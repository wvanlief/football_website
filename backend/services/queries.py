"""API-facing tournament query orchestration.

Read-path functions that load fixtures, standings, and team details for the
HTTP API. Enrichment and grouping live in ``enrichment.py``; knockout
propagation lives in ``knockout.py``.
"""
import os
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session, joinedload

from backend.database import Fixture, PlayerContract, Tournament, TournamentTeam
import backend.crud.fixture as crud_fixture
import backend.crud.player as crud_player
import backend.crud.team as crud_team
from backend.services.enrichment import enrich_fixture, get_timezone, group_enriched_fixtures
from backend.services.knockout import resolve_placeholder_name
from backend.services.simulation import get_probabilities
from backend.services.standings import calculate_points_needed_to_guarantee_top_2, calculate_standings


_FIXTURES_CACHE = {}
_RECOMMENDED_CACHE = {}
_CACHE_TTL = 60  # seconds


def invalidate_fixtures_cache():
    """Clears in-memory fixture response caches."""
    _FIXTURES_CACHE.clear()
    _RECOMMENDED_CACHE.clear()


def get_grouped_fixtures(db: Session, tz_str: str, tournament_id: int = None) -> dict:
    """
    Returns fixtures grouped by time buckets (today, tomorrow, this_week, finished).
    Includes off-season detection and uses in-memory caching for performance.
    """
    use_cache = os.getenv("TESTING") != "True"
    cache_key = (tz_str, tournament_id)
    now = time.time()
    if use_cache and cache_key in _FIXTURES_CACHE:
        cached_time, cached_payload = _FIXTURES_CACHE[cache_key]
        if now - cached_time < _CACHE_TTL:
            return cached_payload

    target_tz = get_timezone(tz_str)
    now_utc = datetime.now(timezone.utc)

    # Fast path for global feed using pre-calculated JSON cache (bypassed in test environment)
    if tournament_id is None and use_cache:
        from backend.services.feed_builder import load_precalculated_feed_cache, build_fixtures_feed_cache
        feed_cache = load_precalculated_feed_cache()
        if not feed_cache:
            feed_cache = build_fixtures_feed_cache(db)

        cached_list = feed_cache.get("fixtures", []) if feed_cache else []
        payload = group_enriched_fixtures(cached_list, target_tz, now_dt=now_utc, updated_at=feed_cache.get("updated_at") if feed_cache else None)
        _FIXTURES_CACHE[cache_key] = (now, payload)
        return payload

    # Specific tournament path or live test environment
    fixtures = crud_fixture.get_eligible_fixtures(db, tournament_id=tournament_id, now_utc=now_utc)
    tts = db.query(TournamentTeam).filter(TournamentTeam.tournament_id == tournament_id).all() if tournament_id else db.query(TournamentTeam).all()

    contracts = db.query(PlayerContract).options(joinedload(PlayerContract.player)).filter(
        PlayerContract.is_active == True
    ).all()
    team_players_map = {}
    for c in contracts:
        team_players_map.setdefault(c.team_id, []).append(c.player)

    team_group_map = {(tt.tournament_id, tt.team_id): tt.group_name for tt in tts}
    enriched_fixtures = [enrich_fixture(f, db, target_tz, team_players_map, team_group_map) for f in fixtures]

    payload = group_enriched_fixtures(enriched_fixtures, target_tz, now_dt=now_utc, updated_at=now_utc.isoformat())
    if use_cache:
        _FIXTURES_CACHE[cache_key] = (now, payload)
    return payload


def get_recommended_fixtures(db: Session, tz_str: str, tournament_id: int = None, min_score: float = 65.0, min_count: int = 7) -> list:
    """
    Returns a list of high-watchability fixtures in Recommended+ tier with guaranteed Top 7 fallback.
    Preloads player and group data to avoid N+1 queries.
    """
    use_cache = os.getenv("TESTING") != "True"
    cache_key = (tz_str, tournament_id, min_score, min_count)
    now = time.time()
    if use_cache and cache_key in _RECOMMENDED_CACHE:
        cached_time, cached_payload = _RECOMMENDED_CACHE[cache_key]
        if now - cached_time < _CACHE_TTL:
            return cached_payload

    target_tz = get_timezone(tz_str)

    # Fast path for global recommended feed using pre-calculated JSON cache
    if tournament_id is None and use_cache:
        from backend.services.feed_builder import load_precalculated_feed_cache, build_fixtures_feed_cache
        feed_cache = load_precalculated_feed_cache()
        if not feed_cache:
            feed_cache = build_fixtures_feed_cache(db)
        if feed_cache:
            all_cached = feed_cache.get("fixtures", [])
            now_utc = datetime.now(timezone.utc)
            future_cached = []
            for f in all_cached:
                dt_str = f.get("date")
                if dt_str:
                    try:
                        f_dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                        if f_dt >= now_utc - timedelta(hours=4):
                            future_cached.append(f)
                    except Exception:
                        future_cached.append(f)
                else:
                    future_cached.append(f)

            recs = [f for f in future_cached if f.get("watchability", {}).get("overall", 0) >= min_score]
            if len(recs) < min_count:
                sorted_f = sorted(future_cached, key=lambda x: x.get("watchability", {}).get("overall", 0), reverse=True)
                recs = sorted_f[:min_count]
            recs.sort(key=lambda x: x.get("watchability", {}).get("overall", 0), reverse=True)
            _RECOMMENDED_CACHE[cache_key] = (now, recs)
            return recs

    if tournament_id is not None:
        fixtures = crud_fixture.get_recommended_fixtures(db, tournament_id=tournament_id, min_score=min_score, min_count=min_count)
        tts = db.query(TournamentTeam).filter(TournamentTeam.tournament_id == tournament_id).all()
    else:
        fixtures = crud_fixture.get_recommended_fixtures(db, tournament_id=None, min_score=min_score, min_count=min_count)
        tts = db.query(TournamentTeam).all()

    # Preload maps to avoid N+1 queries
    contracts = db.query(PlayerContract).options(joinedload(PlayerContract.player)).filter(
        PlayerContract.is_active == True
    ).all()
    team_players_map = {}
    for c in contracts:
        team_players_map.setdefault(c.team_id, []).append(c.player)

    team_group_map = {}
    for tt in tts:
        team_group_map[(tt.tournament_id, tt.team_id)] = tt.group_name

    result = [enrich_fixture(f, db, target_tz, team_players_map, team_group_map) for f in fixtures]
    if use_cache:
        _RECOMMENDED_CACHE[cache_key] = (now, result)
    return result


def get_country_details(db: Session, country_name: str, tz_str: str, tournament_id: int = None) -> dict:
    """
    Returns detailed information about a country/team including Elo, group standings, form, players, and future matches.
    Returns None if the team is not found.
    """
    target_tz = get_timezone(tz_str)
    team = crud_team.get_team_by_name(db, country_name)
    if not team:
        return None

    if tournament_id is None:
        active_tourney = db.query(Tournament).filter(Tournament.status == "Active").first()
        tournament_id = active_tourney.id if active_tourney else None

    contract_type = "Country"
    if tournament_id:
        tourney = db.query(Tournament).filter(Tournament.id == tournament_id).first()
        if tourney and tourney.competition:
            contract_type = "Country" if tourney.competition.type == "International" else "Club"

    tt = db.query(TournamentTeam).filter(
        TournamentTeam.team_id == team.id,
        TournamentTeam.tournament_id == tournament_id
    ).first() if tournament_id else db.query(TournamentTeam).filter(TournamentTeam.team_id == team.id).first()
    group_name = tt.group_name if tt else None

    group_standings = calculate_standings(db, group_name, tournament_id=tournament_id) if group_name else []
    rank = 1
    for index, standing in enumerate(group_standings):
        if standing["name"] == country_name:
            rank = index + 1
            break

    players = crud_player.get_top_players_by_team(db, country_name, contract_type=contract_type, limit=3)
    players_data = [{"name": p.name, "position": p.position, "form": p.form_score} for p in players]

    finished_fixtures = crud_fixture.get_finished_fixtures_for_country(db, country_name, tournament_id=tournament_id)
    finished_fixtures.sort(key=lambda x: x.date_utc, reverse=True)

    form_results = []
    for f in finished_fixtures:
        if f.home_team.name == country_name:
            if f.home_score > f.away_score:
                form_results.append("W")
            elif f.home_score < f.away_score:
                form_results.append("L")
            else:
                form_results.append("D")
        else:
            if f.away_score > f.home_score:
                form_results.append("W")
            elif f.away_score < f.home_score:
                form_results.append("L")
            else:
                form_results.append("D")

    if len(form_results) < 5:
        remaining = 5 - len(form_results)
        elo = team.elo
        if elo >= 2000:
            pad = ["W", "W", "W", "D", "W"]
        elif elo >= 1850:
            pad = ["W", "D", "W", "L", "W"]
        elif elo >= 1700:
            pad = ["D", "L", "W", "D", "W"]
        else:
            pad = ["L", "L", "D", "W", "L"]
        form_results.extend(pad[:remaining])

    form_results = form_results[:5]
    form_results.reverse()

    future_fixtures = crud_fixture.get_future_fixtures_for_country(db, country_name, tournament_id=tournament_id)
    future_fixtures.sort(key=lambda x: x.date_utc)

    # Calculate goals stats
    home_games = db.query(Fixture).filter(Fixture.home_team_id == team.id, Fixture.status == "Finished").all()
    away_games = db.query(Fixture).filter(Fixture.away_team_id == team.id, Fixture.status == "Finished").all()
    goals = sum(g.home_score for g in home_games) + sum(g.away_score for g in away_games)
    played = len(home_games) + len(away_games)
    avg_goals = goals / played if played > 0 else 0.0
    is_high_scoring = (played >= 3 and avg_goals >= 1.75) or (played > 0 and played < 3 and avg_goals >= 2.0)

    # Preload maps to avoid N+1 queries
    contracts = db.query(PlayerContract).options(joinedload(PlayerContract.player)).filter(
        PlayerContract.type == contract_type,
        PlayerContract.is_active == True
    ).all()
    team_players_map = {}
    for c in contracts:
        team_players_map.setdefault(c.team_id, []).append(c.player)

    tts = db.query(TournamentTeam).filter(TournamentTeam.tournament_id == tournament_id).all() if tournament_id else db.query(TournamentTeam).all()
    team_group_map = {}
    for t_t in tts:
        team_group_map[(t_t.tournament_id, t_t.team_id)] = t_t.group_name

    future_matches_data = [enrich_fixture(f, db, target_tz, team_players_map, team_group_map) for f in future_fixtures]

    return {
        "name": team.name,
        "elo": team.elo,
        "logo_url": team.badge_url,
        "group_name": group_name,
        "group_rank": rank,
        "form": form_results,
        "players": players_data,
        "future_matches": future_matches_data,
        "is_high_scoring": is_high_scoring,
        "avg_goals_scored": round(avg_goals, 2)
    }


def get_all_third_placed_teams(db: Session, tournament_id: int = None) -> list:
    """
    Returns a list of all third-placed teams across groups, sorted by points, goal difference, and Elo.
    Includes qualification probabilities from simulation results if available.
    """
    if tournament_id is None:
        active_tourney = db.query(Tournament).filter(Tournament.status == "Active").first()
        tournament_id = active_tourney.id if active_tourney else None

    groups = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L"]
    third_placed = []

    sim_data = get_probabilities(tournament_id)
    team_probs = {}
    if sim_data and "probabilities" in sim_data:
        for p in sim_data["probabilities"]:
            team_probs[p["team"]] = p

    for g in groups:
        standings = calculate_standings(db, g, tournament_id=tournament_id)
        if len(standings) < 3:
            continue

        team_standing = standings[2].copy()
        team_standing["group"] = g

        prob_data = team_probs.get(team_standing["name"])
        if prob_data:
            team_standing["qualification_probability"] = round(prob_data["r32_exit_pct"] + prob_data["r16_exit_pct"] + prob_data["qf_exit_pct"] + prob_data["sf_exit_pct"] + prob_data["runner_up_pct"] + prob_data["champion_pct"], 2)
            if team_standing["qualification_probability"] == 0.0:
                team_standing["status"] = "Eliminated"
            else:
                team_standing["status"] = "Active"
        else:
            team_standing["qualification_probability"] = None
            team_standing["status"] = "Active"

        third_placed.append(team_standing)

    third_placed.sort(key=lambda x: (x["points"], x["goal_difference"], x["goals_for"], x["elo"]), reverse=True)
    return third_placed


def get_group_details(db: Session, group_letter: str, tz_str: str, tournament_id: int = None) -> dict:
    """
    Returns detailed standings and fixtures for a specific group.
    Includes qualification probabilities and points needed for top 2 finish.
    """
    target_tz = get_timezone(tz_str)

    if tournament_id is None:
        active_tourney = db.query(Tournament).filter(Tournament.status == "Active").first()
        tournament_id = active_tourney.id if active_tourney else None

    contract_type = "Country"
    if tournament_id:
        tourney = db.query(Tournament).filter(Tournament.id == tournament_id).first()
        if tourney and tourney.competition:
            contract_type = "Country" if tourney.competition.type == "International" else "Club"

    if group_letter and group_letter.lower() == "standings":
        teams = crud_team.get_all_teams(db, tournament_id=tournament_id)
    else:
        teams = crud_team.get_teams_by_group(db, group_letter, tournament_id=tournament_id)
    if not teams:
        return None

    standings = calculate_standings(db, group_letter, tournament_id=tournament_id)

    sim_data = get_probabilities(tournament_id)
    team_probs = {}
    if sim_data and "probabilities" in sim_data:
        for p in sim_data["probabilities"]:
            team_probs[p["team"]] = p

    for s in standings:
        prob_data = team_probs.get(s["name"])
        if prob_data:
            s["qualification_probability"] = round(100.0 - prob_data["group_exit_pct"], 2)
            if prob_data["group_exit_pct"] == 0.0:
                s["status"] = "Qualified"
            elif prob_data["group_exit_pct"] == 100.0:
                s["status"] = "Eliminated"
            else:
                s["status"] = "Active"
        else:
            s["qualification_probability"] = None
            s["status"] = "Active"

        if group_letter and group_letter.lower() == "standings":
            s["points_needed_top_2"] = None
        else:
            s["points_needed_top_2"] = calculate_points_needed_to_guarantee_top_2(db, s["name"], group_letter, tournament_id=tournament_id)

    team_names = [t.name for t in teams]
    fixtures = crud_fixture.get_fixtures_for_group(db, team_names, tournament_id=tournament_id)

    # Preload maps to avoid N+1 queries
    contracts = db.query(PlayerContract).options(joinedload(PlayerContract.player)).filter(
        PlayerContract.type == contract_type,
        PlayerContract.is_active == True
    ).all()
    team_players_map = {}
    for c in contracts:
        team_players_map.setdefault(c.team_id, []).append(c.player)

    tts = db.query(TournamentTeam).filter(TournamentTeam.tournament_id == tournament_id).all() if tournament_id else db.query(TournamentTeam).all()
    team_group_map = {}
    for tt in tts:
        team_group_map[(tt.tournament_id, tt.team_id)] = tt.group_name

    fixtures_data = [enrich_fixture(f, db, target_tz, team_players_map, team_group_map) for f in fixtures]

    return {
        "group_letter": group_letter,
        "standings": standings,
        "fixtures": fixtures_data
    }


def get_calendar_fixtures(db: Session, tz_str: str, tournament_id: int = None, start_date_str: str = None, end_date_str: str = None) -> list:
    """
    Returns fixtures within a date range (defaults to 30 days past, 60 days future).
    Returns lightweight fixture data suitable for calendar views.
    """
    target_tz = get_timezone(tz_str)
    today_dt = datetime.now(target_tz)

    if tournament_id is None:
        active_tourney = db.query(Tournament).filter(Tournament.status == "Active").first()
        tournament_id = active_tourney.id if active_tourney else None

    # Default to 30 days back, 60 days forward (90 days total window)
    if start_date_str:
        try:
            parsed = datetime.strptime(start_date_str, "%Y-%m-%d")
            start_date = datetime(parsed.year, parsed.month, parsed.day, 0, 0, 0, tzinfo=target_tz)
        except ValueError:
            start_date = (today_dt - timedelta(days=30)).replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        start_date = (today_dt - timedelta(days=30)).replace(hour=0, minute=0, second=0, microsecond=0)

    if end_date_str:
        try:
            parsed = datetime.strptime(end_date_str, "%Y-%m-%d")
            end_date = datetime(parsed.year, parsed.month, parsed.day, 23, 59, 59, 999999, tzinfo=target_tz)
        except ValueError:
            end_date = (today_dt + timedelta(days=60)).replace(hour=23, minute=59, second=59, microsecond=999999)
    else:
        end_date = (today_dt + timedelta(days=60)).replace(hour=23, minute=59, second=59, microsecond=999999)

    start_utc = start_date.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
    end_utc = end_date.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)

    q = db.query(Fixture).options(
        joinedload(Fixture.home_team),
        joinedload(Fixture.away_team)
    ).filter(
        Fixture.date_utc >= start_utc,
        Fixture.date_utc <= end_utc
    )
    if tournament_id is not None:
        q = q.filter(Fixture.tournament_id == tournament_id)
    fixtures = q.all()

    fixtures.sort(key=lambda x: x.date_utc)

    tts = db.query(TournamentTeam).filter(TournamentTeam.tournament_id == tournament_id).all() if tournament_id else db.query(TournamentTeam).all()
    team_group_map = {}
    for tt in tts:
        team_group_map[(tt.tournament_id, tt.team_id)] = tt.group_name

    calendar_data = []
    for f in fixtures:
        dt = f.date_utc
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ZoneInfo("UTC"))
        dt_tz = dt.astimezone(target_tz)

        group_letter = team_group_map.get((f.tournament_id, f.home_team_id))
        display_stage = f"Group {group_letter}" if f.stage == "Group Stage" and group_letter else f.stage

        calendar_data.append({
            "id": f.id,
            "home_team": {
                "name": f.home_team.name if f.home_team else resolve_placeholder_name(db, f.home_team_placeholder, f.tournament_id),
                "logo_url": f.home_team.badge_url if f.home_team else "/static/badges/default.png"
            },
            "away_team": {
                "name": f.away_team.name if f.away_team else resolve_placeholder_name(db, f.away_team_placeholder, f.tournament_id),
                "logo_url": f.away_team.badge_url if f.away_team else "/static/badges/default.png"
            },
            "date": f.date_utc.isoformat(),
            "formatted_time": dt_tz.strftime("%H:%M"),
            "formatted_date": dt_tz.strftime("%B %d, %Y"),
            "formatted_date_short": dt_tz.strftime("%b %d"),
            "stage": display_stage,
            "status": f.status,
            "score": f"{f.home_score} - {f.away_score}" if f.status in ("Finished", "Live") and f.home_score is not None and f.away_score is not None else None,
            "watchability_score": f.watchability_score
        })

    return calendar_data


def get_fixture_details_by_id(db: Session, fixture_id: int, tz_str: str) -> dict:
    """
    Returns enriched fixture details for a specific fixture ID.
    Returns None if the fixture is not found.
    """
    target_tz = get_timezone(tz_str)
    f = db.query(Fixture).filter(Fixture.id == fixture_id).first()
    if not f:
        return None
    return enrich_fixture(f, db, target_tz)


def evaluate_nations_league_promotions(db: Session, tournament_id: int):
    """
    Evaluates completed groups in the UEFA Nations League and updates promoted/relegated
    statuses on TournamentTeam models, and prints/logs the outcomes.
    """
    tourney = db.query(Tournament).filter(Tournament.id == tournament_id).first()
    if not tourney or not tourney.competition or tourney.competition.format_engine != "nations_league":
        return

    tts = db.query(TournamentTeam).filter(TournamentTeam.tournament_id == tournament_id).all()
    groups_map = {}
    for tt in tts:
        if tt.division and tt.group_name:
            key = f"{tt.division}{tt.group_name}"
            if key not in groups_map:
                groups_map[key] = []
            groups_map[key].append(tt)

    for group_key, group_tts in groups_map.items():
        standings = calculate_standings(db, group_key, tournament_id=tournament_id)

        team_names = [tt.team.name for tt in group_tts]
        group_fixtures = crud_fixture.get_fixtures_for_group(db, team_names, tournament_id=tournament_id)

        is_completed = len(group_fixtures) > 0 and all(f.status == "Finished" for f in group_fixtures)

        if is_completed:
            tt_by_name = {tt.team.name: tt for tt in group_tts}
            div = group_key[0]  # 'A', 'B', 'C', 'D'

            for index, standing in enumerate(standings):
                team_name = standing["name"]
                rank = index + 1
                tt = tt_by_name[team_name]

                tt.promoted = False
                tt.relegated = False

                if rank == 1:
                    if div != 'A':
                        tt.promoted = True
                elif rank == 4:
                    if div != 'D':
                        tt.relegated = True
            db.commit()
