import os
import json
import time
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
from sqlalchemy.orm import Session, joinedload

_FIXTURES_CACHE = {}
_RECOMMENDED_CACHE = {}
_CACHE_TTL = 60  # seconds

def invalidate_fixtures_cache():
    """Clears in-memory fixture response caches."""
    _FIXTURES_CACHE.clear()
    _RECOMMENDED_CACHE.clear()

from backend.database import Fixture, Team, Player, PlayerContract, TournamentTeam, Tournament, Competition
import backend.crud.fixture as crud_fixture
import backend.crud.team as crud_team
import backend.crud.player as crud_player
from backend.services.standings import calculate_standings, calculate_points_needed_to_guarantee_top_2


NEXT_ROUND_LOOKUP = {
    73: (90, "home"), 74: (89, "home"), 75: (90, "away"), 76: (91, "home"),
    77: (89, "away"), 78: (91, "away"), 79: (92, "home"), 80: (92, "away"),
    81: (94, "home"), 82: (94, "away"), 83: (93, "home"), 84: (93, "away"),
    85: (96, "home"), 86: (95, "home"), 87: (96, "away"), 88: (95, "away"),
    89: (97, "home"), 90: (97, "away"), 91: (99, "home"), 92: (99, "away"),
    93: (98, "home"), 94: (98, "away"), 95: (100, "home"), 96: (100, "away"),
    97: (101, "home"), 98: (101, "away"), 99: (102, "home"), 100: (102, "away"),
    101: (104, "home"), 102: (104, "away")
}

def propagate_knockout_fixtures(db: Session):
    """
    Scans finished knockout fixtures in the database and propagates winners/losers
    to subsequent rounds using data-driven fixture_dependencies.
    """
    fixtures = db.query(Fixture).all()
    fixtures_by_id = {f.id: f for f in fixtures}
    fixtures_by_api_id = {f.api_id: f for f in fixtures if f.api_id}
    
    modified_fixtures = set()
    
    updated = True
    iterations = 0
    while updated and iterations < 10:
        updated = False
        iterations += 1
        
        for f in fixtures:
            if f.status != "Finished" or f.stage == "Group Stage" or f.stage == "Regular Season" or f.stage == "League Phase":
                continue
                
            if f.leg_number == 1:
                # Two-legged ties only propagate after leg 2 is played
                leg2 = db.query(Fixture).filter(
                    Fixture.tournament_id == f.tournament_id,
                    Fixture.stage == f.stage,
                    Fixture.leg_number == 2,
                    ((Fixture.home_team_id == f.away_team_id) & (Fixture.away_team_id == f.home_team_id)) |
                    ((Fixture.home_team_id == f.home_team_id) & (Fixture.away_team_id == f.away_team_id))
                ).first()
                if leg2:
                    continue

            winner_id = f.winner_id
            if not winner_id:
                if f.leg_number == 2:
                    # Find corresponding leg 1 fixture: opposite teams, leg 1, same tournament and stage
                    leg1 = db.query(Fixture).filter(
                        Fixture.tournament_id == f.tournament_id,
                        Fixture.stage == f.stage,
                        Fixture.home_team_id == f.away_team_id,
                        Fixture.away_team_id == f.home_team_id,
                        Fixture.leg_number == 1
                    ).first()
                    if leg1 and leg1.home_score is not None and leg1.away_score is not None and f.home_score is not None and f.away_score is not None:
                        agg_home = f.home_score + leg1.away_score
                        agg_away = f.away_score + leg1.home_score
                        if agg_home > agg_away:
                            winner_id = f.home_team_id
                        elif agg_home < agg_away:
                            winner_id = f.away_team_id
                        else:
                            if f.home_penalty_score is not None and f.away_penalty_score is not None:
                                winner_id = f.home_team_id if f.home_penalty_score > f.away_penalty_score else f.away_team_id
                else:
                    # Single-leg tie winner determination
                    if f.home_score is not None and f.away_score is not None:
                        if f.home_score > f.away_score:
                            winner_id = f.home_team_id
                        elif f.home_score < f.away_score:
                            winner_id = f.away_team_id
                        else:
                            if f.home_penalty_score is not None and f.away_penalty_score is not None:
                                winner_id = f.home_team_id if f.home_penalty_score > f.away_penalty_score else f.away_team_id
                                
            if not winner_id:
                continue
                
            loser_id = f.away_team_id if winner_id == f.home_team_id else f.home_team_id
            
            # Try to query dependencies from DB first
            from backend.database import FixtureDependency
            dependencies = db.query(FixtureDependency).filter(FixtureDependency.source_fixture_id == f.id).all()
            
            if dependencies:
                # DB-driven propagation
                for dep in dependencies:
                    target_fixture = fixtures_by_id.get(dep.target_fixture_id)
                    if not target_fixture:
                        continue
                    prog_team_id = winner_id if dep.result_type == "winner" else loser_id
                    if not prog_team_id:
                        continue
                        
                    if dep.slot == "home":
                        if target_fixture.home_team_id != prog_team_id:
                            target_fixture.home_team_id = prog_team_id
                            target_fixture.home_team_placeholder = None
                            updated = True
                            modified_fixtures.add(target_fixture)
                    elif dep.slot == "away":
                        if target_fixture.away_team_id != prog_team_id:
                            target_fixture.away_team_id = prog_team_id
                            target_fixture.away_team_placeholder = None
                            updated = True
                            modified_fixtures.add(target_fixture)
            else:
                # Backwards compatibility fallback to NEXT_ROUND_LOOKUP for World Cup
                if not f.api_id:
                    continue
                try:
                    match_num = int(f.api_id)
                except ValueError:
                    continue
                    
                # 1. Standard next-round propagation
                next_info = NEXT_ROUND_LOOKUP.get(match_num)
                if next_info:
                    next_match_num, slot = next_info
                    next_fixture = fixtures_by_api_id.get(str(next_match_num))
                    if next_fixture:
                        if slot == "home":
                            if next_fixture.home_team_id != winner_id:
                                next_fixture.home_team_id = winner_id
                                next_fixture.home_team_placeholder = None
                                updated = True
                                modified_fixtures.add(next_fixture)
                        elif slot == "away":
                            if next_fixture.away_team_id != winner_id:
                                next_fixture.away_team_id = winner_id
                                next_fixture.away_team_placeholder = None
                                updated = True
                                modified_fixtures.add(next_fixture)
                                
                # 2. Third-place play-off (api_id 103) is populated by the losers of match 101 and 102
                if match_num == 101:
                    third_fixture = fixtures_by_api_id.get("103")
                    if third_fixture and third_fixture.home_team_id != loser_id:
                        third_fixture.home_team_id = loser_id
                        third_fixture.home_team_placeholder = None
                        updated = True
                        modified_fixtures.add(third_fixture)
                elif match_num == 102:
                    third_fixture = fixtures_by_api_id.get("103")
                    if third_fixture and third_fixture.away_team_id != loser_id:
                        third_fixture.away_team_id = loser_id
                        third_fixture.away_team_placeholder = None
                        updated = True
                        modified_fixtures.add(third_fixture)

    if modified_fixtures:
        from backend.ingestor import calculate_default_odds
        from backend.database import FixtureOdds
        from datetime import timezone
        
        now_time = datetime.now(timezone.utc)
        for fixture in modified_fixtures:
            h_elo = fixture.home_team.elo if fixture.home_team else 1700
            a_elo = fixture.away_team.elo if fixture.away_team else 1700
            odds_h, odds_d, odds_a = calculate_default_odds(h_elo, a_elo)
            
            db_odds = FixtureOdds(
                fixture_id=fixture.id,
                recorded_at=now_time,
                odds_home=odds_h,
                odds_draw=odds_d,
                odds_away=odds_a
            )
            db.add(db_odds)

def get_timezone(tz_str: str) -> ZoneInfo:
    try:
        return ZoneInfo(tz_str)
    except Exception:
        return ZoneInfo("UTC")

def resolve_placeholder_name(db: Session, placeholder: str, tournament_id: int) -> str:
    if not placeholder:
        return "TBD"
    import re
    match_ref = re.search(r"Match (\d+)", placeholder)
    if match_ref:
        ref_api_id = match_ref.group(1)
        # Look up referenced fixture
        ref_fixture = db.query(Fixture).filter(
            Fixture.tournament_id == tournament_id,
            Fixture.api_id == ref_api_id
        ).first()
        if ref_fixture:
            h_name = ref_fixture.home_team.name if ref_fixture.home_team else ref_fixture.home_team_placeholder
            a_name = ref_fixture.away_team.name if ref_fixture.away_team else ref_fixture.away_team_placeholder
            if h_name and a_name:
                # Simplify common labels to make them shorter
                def simplify(name):
                    return name.replace("Runner-up Group ", "Runner-up ").replace("Winner Group ", "Winner ")
                return f"{placeholder} ({simplify(h_name)} or {simplify(a_name)})"
    return placeholder

def enrich_fixture(f: Fixture, db: Session, target_tz: ZoneInfo, team_players_map: dict = None, team_group_map: dict = None) -> dict:
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
        "date": f.date_utc.isoformat(),
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
            "overall": f.watchability_score,
            "competitiveness": f.competitiveness_score,
            "odds": f.odds_score,
            "form": f.form_score,
            "narrative": f.narrative_score
        },
        "reasons": reasons
    }

def get_grouped_fixtures(db: Session, tz_str: str, tournament_id: int = None) -> dict:
    use_cache = os.getenv("TESTING") != "True"
    cache_key = (tz_str, tournament_id)
    now = time.time()
    if use_cache and cache_key in _FIXTURES_CACHE:
        cached_time, cached_payload = _FIXTURES_CACHE[cache_key]
        if now - cached_time < _CACHE_TTL:
            return cached_payload
            
    target_tz = get_timezone(tz_str)
    
    if tournament_id is not None:
        fixtures = crud_fixture.get_all_fixtures(db, tournament_id=tournament_id)
        tts = db.query(TournamentTeam).filter(TournamentTeam.tournament_id == tournament_id).all()
    else:
        fixtures = crud_fixture.get_all_fixtures(db, tournament_id=None)
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

        
    today_fixtures = []
    tomorrow_fixtures = []
    week_fixtures = []
    finished_fixtures = []
    scheduled_fixtures = []
    
    today_date = datetime.now(target_tz).date()
    tomorrow_date = today_date + timedelta(days=1)
    max_date = today_date + timedelta(days=8)
    
    for f in fixtures:
        dt = f.date_utc
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ZoneInfo("UTC"))
        dt_tz = dt.astimezone(target_tz)
        match_date = dt_tz.date()
        
        fixture_data = enrich_fixture(f, db, target_tz, team_players_map, team_group_map)
        
        if fixture_data["status"] == "Finished":
            finished_fixtures.append(fixture_data)
            continue
            
        scheduled_fixtures.append((match_date, fixture_data))
        
        if match_date == today_date:
            today_fixtures.append(fixture_data)
        elif match_date == tomorrow_date:
            tomorrow_fixtures.append(fixture_data)
        elif tomorrow_date < match_date <= max_date:
            week_fixtures.append(fixture_data)
            
    is_offseason = False
    offseason_notice = None
    
    # Off-season date anchor: If no upcoming matches in the next 8 days, find the earliest upcoming matchday
    if not today_fixtures and not tomorrow_fixtures and not week_fixtures and scheduled_fixtures:
        scheduled_fixtures.sort(key=lambda x: x[0])
        earliest_date = scheduled_fixtures[0][0]
        matchday_end = earliest_date + timedelta(days=3)
        
        upcoming_block = [data for m_date, data in scheduled_fixtures if earliest_date <= m_date <= matchday_end]
        upcoming_block.sort(key=lambda x: x["watchability"]["overall"], reverse=True)
        week_fixtures = upcoming_block
        is_offseason = True
        formatted_start = earliest_date.strftime("%B %d, %Y")
        offseason_notice = f"Off-Season: Showing upcoming Gameweek 1 blockbusters starting {formatted_start}"
        
    today_fixtures.sort(key=lambda x: x["date"])
    tomorrow_fixtures.sort(key=lambda x: x["date"])
    week_fixtures.sort(key=lambda x: x["watchability"]["overall"], reverse=True)
    finished_fixtures.sort(key=lambda x: x["date"], reverse=True)
    
    result = {
        "today": today_fixtures,
        "tomorrow": tomorrow_fixtures,
        "this_week": week_fixtures[:5],
        "finished": finished_fixtures,
        "is_offseason": is_offseason,
        "offseason_notice": offseason_notice
    }
    if use_cache:
        _FIXTURES_CACHE[cache_key] = (now, result)
    return result

def get_recommended_fixtures(db: Session, tz_str: str, tournament_id: int = None, min_score: float = 75.0) -> list:
    use_cache = os.getenv("TESTING") != "True"
    cache_key = (tz_str, tournament_id, min_score)
    now = time.time()
    if use_cache and cache_key in _RECOMMENDED_CACHE:
        cached_time, cached_payload = _RECOMMENDED_CACHE[cache_key]
        if now - cached_time < _CACHE_TTL:
            return cached_payload
            
    target_tz = get_timezone(tz_str)
    
    if tournament_id is not None:
        fixtures = crud_fixture.get_recommended_fixtures(db, tournament_id=tournament_id, min_score=min_score)
        tts = db.query(TournamentTeam).filter(TournamentTeam.tournament_id == tournament_id).all()
    else:
        fixtures = crud_fixture.get_recommended_fixtures(db, tournament_id=None, min_score=min_score)
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
        "group_name": group_name,
        "group_rank": rank,
        "form": form_results,
        "players": players_data,
        "future_matches": future_matches_data,
        "is_high_scoring": is_high_scoring,
        "avg_goals_scored": round(avg_goals, 2)
    }




def get_all_third_placed_teams(db: Session, tournament_id: int = None) -> list:
    if tournament_id is None:
        active_tourney = db.query(Tournament).filter(Tournament.status == "Active").first()
        tournament_id = active_tourney.id if active_tourney else None
        
    groups = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L"]
    third_placed = []
    
    sim_data = None
    if tournament_id == 1:
        file_path = os.path.join(os.path.dirname(__file__), "..", "data", "simulation_results.json")
        if os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    sim_data = json.load(f)
            except Exception:
                pass
            
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
    
    sim_data = None
    if tournament_id == 1:
        file_path = os.path.join(os.path.dirname(__file__), "..", "data", "simulation_results.json")
        if os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    sim_data = json.load(f)
            except Exception:
                pass
            
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
                "name": f.home_team.name if f.home_team else resolve_placeholder_name(db, f.home_team_placeholder, f.tournament_id)
            },
            "away_team": {
                "name": f.away_team.name if f.away_team else resolve_placeholder_name(db, f.away_team_placeholder, f.tournament_id)
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
    from backend.database import TournamentTeam, Tournament
    
    tourney = db.query(Tournament).filter(Tournament.id == tournament_id).first()
    if not tourney or not tourney.competition or tourney.competition.format_engine != "nations_league":
        return

    # Find all groups/divisions
    tts = db.query(TournamentTeam).filter(TournamentTeam.tournament_id == tournament_id).all()
    # Group teams by division and group_name
    groups_map = {}
    for tt in tts:
        if tt.division and tt.group_name:
            key = f"{tt.division}{tt.group_name}"
            if key not in groups_map:
                groups_map[key] = []
            groups_map[key].append(tt)

    for group_key, group_tts in groups_map.items():
        # Get standings for this specific group
        standings = calculate_standings(db, group_key, tournament_id=tournament_id)
        
        # Check if group is fully finished
        team_names = [tt.team.name for tt in group_tts]
        from backend.crud.fixture import get_fixtures_for_group
        group_fixtures = get_fixtures_for_group(db, team_names, tournament_id=tournament_id)
        
        is_completed = len(group_fixtures) > 0 and all(f.status == "Finished" for f in group_fixtures)
        
        if is_completed:
            tt_by_name = {tt.team.name: tt for tt in group_tts}
            div = group_key[0] # 'A', 'B', 'C', 'D'
            
            for index, standing in enumerate(standings):
                team_name = standing["name"]
                rank = index + 1
                tt = tt_by_name[team_name]
                
                # Reset first
                tt.promoted = False
                tt.relegated = False
                
                if rank == 1:
                    if div != 'A':
                        tt.promoted = True
                elif rank == 4:
                    if div != 'D':
                        tt.relegated = True
            db.commit()


