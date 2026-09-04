"""Fixture enrichment and time-bucket grouping.

Read-path helpers that turn ORM fixtures into API dictionaries and group them
into Today / Tomorrow / This Week / Finished buckets. Shared by query
orchestration and the pre-calculated feed builder.
"""
import json
from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from backend.database import Fixture, TournamentTeam
import backend.crud.player as crud_player
from backend.scoring import calculate_global_percentile, get_score_tier
from backend.services.knockout import resolve_placeholder_name


def get_timezone(tz_str: str) -> ZoneInfo:
    """
    Returns a ZoneInfo object for the given timezone string, falling back to UTC if invalid.
    """
    try:
        return ZoneInfo(tz_str)
    except Exception:
        return ZoneInfo("UTC")


def enrich_fixture(f: Fixture, db: Session, target_tz: ZoneInfo, team_players_map: dict = None, team_group_map: dict = None) -> dict:
    """
    Enriches a Fixture model into a dictionary with formatted dates, team details, players, and watchability scores.
    Optimized for N+1 query prevention via optional preloaded maps.
    """
    dt = f.date_utc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    dt_tz = dt.astimezone(target_tz)

    home_team = f.home_team
    away_team = f.away_team

    # Get group letter
    group_letter = None
    if team_group_map is not None:
        group_letter = team_group_map.get((f.tournament_id, f.home_team_id))
    else:
        tt = db.query(TournamentTeam).filter(
            TournamentTeam.tournament_id == f.tournament_id,
            TournamentTeam.team_id == f.home_team_id
        ).first()
        if tt:
            group_letter = tt.group_name

    # Determine contract type (Club vs Country) based on competition type
    comp = f.tournament.competition if f.tournament else None
    contract_type = "Country" if comp and comp.type == "International" else "Club"

    # Get players
    if team_players_map is not None:
        home_players = team_players_map.get(f.home_team_id, [])
        away_players = team_players_map.get(f.away_team_id, [])
    else:
        home_players = crud_player.get_players_by_team(db, home_team.name, contract_type=contract_type) if home_team else []
        away_players = crud_player.get_players_by_team(db, away_team.name, contract_type=contract_type) if away_team else []

    reasons = []
    try:
        reasons = json.loads(f.reasons_json) if f.reasons_json else []
    except Exception:
        pass

    display_stage = f"Group {group_letter}" if f.stage == "Group Stage" and group_letter else f.stage
    latest_odds = f.latest_odds

    comp_name = comp.name if comp else None
    comp_badge = comp.badge if comp else "⚽"
    overall_score = f.watchability_score or 0.0
    global_pct = calculate_global_percentile(overall_score)
    global_tier = get_score_tier(overall_score)

    return {
        "id": f.id,
        "tournament_id": f.tournament_id,
        "competition_name": comp_name,
        "competition_badge": comp_badge,
        "home_team": {
            "name": home_team.name if home_team else resolve_placeholder_name(db, f.home_team_placeholder, f.tournament_id),
            "elo": home_team.elo if home_team else 1500,
            "form_score": home_team.form_score if home_team else 50.0,
            "win_streak": home_team.win_streak if home_team else 0,
            "logo_url": home_team.badge_url if home_team else "/static/badges/default.png",
            "players": [{"name": p.name, "position": p.position, "form": p.form_score} for p in home_players]
        },
        "away_team": {
            "name": away_team.name if away_team else resolve_placeholder_name(db, f.away_team_placeholder, f.tournament_id),
            "elo": away_team.elo if away_team else 1500,
            "form_score": away_team.form_score if away_team else 50.0,
            "win_streak": away_team.win_streak if away_team else 0,
            "logo_url": away_team.badge_url if away_team else "/static/badges/default.png",
            "players": [{"name": p.name, "position": p.position, "form": p.form_score} for p in away_players]
        },
        "date": dt.isoformat(),
        "formatted_time": dt_tz.strftime("%H:%M"),
        "formatted_date": dt_tz.strftime("%B %d, %Y"),
        "formatted_date_short": dt_tz.strftime("%b %d"),
        "stage": display_stage,
        "group_name": group_letter,
        "status": f.status,
        "score": f"{f.home_score} - {f.away_score}" if f.status in ("Finished", "Live") and f.home_score is not None and f.away_score is not None else None,
        "odds": {
            "home": latest_odds.odds_home,
            "draw": latest_odds.odds_draw,
            "away": latest_odds.odds_away
        },
        "watchability": {
            "overall": overall_score,
            "competitiveness": f.competitiveness_score,
            "odds": f.odds_score,
            "form": f.form_score,
            "narrative": f.narrative_score,
            "percentile": global_pct,
            "tier": global_tier,
            "context_label": None
        },
        "reasons": reasons
    }


def group_enriched_fixtures(
    enriched_fixtures: list[dict],
    target_tz: ZoneInfo,
    now_dt: Optional[datetime] = None,
    updated_at: Optional[str] = None
) -> dict:
    """
    Groups enriched fixture dictionaries into Today, Tomorrow, This Week (8-day window),
    and Finished buckets according to target_tz.
    Handles off-season detection and high-quality gems filtering canonically.
    """
    if now_dt is None:
        now_dt = datetime.now(timezone.utc)
    if now_dt.tzinfo is None:
        now_dt = now_dt.replace(tzinfo=timezone.utc)

    now_tz = now_dt.astimezone(target_tz)
    today_date = now_tz.date()
    tomorrow_date = today_date + timedelta(days=1)
    max_date = today_date + timedelta(days=8)

    today_fixtures = []
    tomorrow_fixtures = []
    week_fixtures = []
    finished_fixtures = []
    scheduled_fixtures = []

    for fdata in enriched_fixtures:
        dt_str = fdata.get("date")
        if dt_str:
            dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
            dt_tz = dt.astimezone(target_tz)
            match_date = dt_tz.date()
            fdata["date"] = dt_tz.isoformat()
        else:
            match_date = today_date

        if fdata.get("status") == "Finished":
            finished_fixtures.append(fdata)
            continue

        if match_date >= today_date:
            scheduled_fixtures.append((match_date, fdata))

        if match_date == today_date:
            today_fixtures.append(fdata)
        elif match_date == tomorrow_date:
            tomorrow_fixtures.append(fdata)
        elif tomorrow_date < match_date <= max_date:
            week_fixtures.append(fdata)

    # Sort today and tomorrow by ascending kick-off time
    today_fixtures.sort(key=lambda x: x.get("date") or "")
    tomorrow_fixtures.sort(key=lambda x: x.get("date") or "")
    # Sort finished descending by date
    finished_fixtures.sort(key=lambda x: x.get("date") or "", reverse=True)

    # Assign contextual rank label for today's top match
    if today_fixtures:
        best_today = max(today_fixtures, key=lambda x: x.get("watchability", {}).get("overall", 0))
        if best_today.get("watchability"):
            best_today["watchability"]["context_label"] = "🔥 #1 Match Today"

    is_offseason = False
    offseason_notice = None

    if not today_fixtures and not tomorrow_fixtures and not week_fixtures and scheduled_fixtures:
        is_offseason = True
        scheduled_fixtures.sort(key=lambda x: x[0])
        first_match_date = scheduled_fixtures[0][0]
        upcoming_block = []
        for m_date, f_data in scheduled_fixtures:
            if first_match_date <= m_date <= first_match_date + timedelta(days=8):
                upcoming_block.append(f_data)
        upcoming_block.sort(key=lambda x: x.get("watchability", {}).get("overall", 0), reverse=True)
        week_fixtures = upcoming_block[:8]
        offseason_notice = f"Off-season: Showing next upcoming matches starting {first_match_date.strftime('%b %d, %Y')}."
    else:
        # Upcoming Recommended+: Filter by watchability score >= 65.0 (Recommended tier / Top 20%) and rank descending
        high_quality = [
            f for f in week_fixtures
            if f.get("watchability", {}).get("overall", 0) >= 65.0
        ]
        high_quality.sort(key=lambda x: x.get("watchability", {}).get("overall", 0), reverse=True)

        if len(high_quality) >= 3:
            week_fixtures = high_quality[:8]
        else:
            # Quiet week fallback: top 7 highest-rated matches in the 8-day window
            week_fixtures.sort(key=lambda x: x.get("watchability", {}).get("overall", 0), reverse=True)
            week_fixtures = week_fixtures[:7]

    # Assign contextual rank labels for top weekly matches
    for idx, f in enumerate(week_fixtures):
        w_obj = f.get("watchability")
        if w_obj and not w_obj.get("context_label"):
            if idx == 0:
                w_obj["context_label"] = "🏆 #1 This Week"
            elif idx in (1, 2):
                w_obj["context_label"] = "Top 3 This Week"

    return {
        "today": today_fixtures,
        "tomorrow": tomorrow_fixtures,
        "this_week": week_fixtures,
        "finished": finished_fixtures[:30],
        "is_offseason": is_offseason,
        "offseason_notice": offseason_notice,
        "updated_at": updated_at or datetime.now(timezone.utc).isoformat()
    }
