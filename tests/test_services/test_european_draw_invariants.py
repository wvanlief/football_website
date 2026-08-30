import json
from pathlib import Path
from collections import defaultdict
import pytest
from backend.services.seeder import seed_european_cups
from backend.database import Competition, Tournament, Fixture, Team

def test_european_draw_json_invariants():
    """
    Strict mathematical validation of openfootball 36-team Swiss draw & knockout dataset.
    """
    draw_file = Path("backend/data/european_draw_2026.json")
    assert draw_file.exists(), "european_draw_2026.json must exist"

    with open(draw_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 1. Competitions check
    expected_comps = ["UEFA Champions League", "UEFA Europa League", "UEFA Conference League"]
    for comp in expected_comps:
        assert comp in data, f"{comp} missing in draw dataset"

    # 2. UCL Invariants (36 teams, 8 matchdays, 18 matches/matchday = 144 fixtures)
    ucl = data["UEFA Champions League"]
    assert len(ucl["teams"]) == 36, "UCL must have exactly 36 teams"
    
    ucl_league = [f for f in ucl["fixtures"] if f.get("stage") == "League Phase"]
    assert len(ucl_league) == 144, f"UCL must have exactly 144 League Phase fixtures, found {len(ucl_league)}"
    
    ucl_team_names = {t["name"] for t in ucl["teams"]}
    assert len(ucl_team_names) == 36, "All 36 UCL team names must be unique"

    home_counts = defaultdict(int)
    away_counts = defaultdict(int)
    opponents = defaultdict(set)
    matchday_counts = defaultdict(int)

    for f in ucl_league:
        home, away = f["home"], f["away"]
        assert home in ucl_team_names, f"Unknown home team: {home}"
        assert away in ucl_team_names, f"Unknown away team: {away}"
        assert home != away, f"Self match detected: {home}"
        
        home_counts[home] += 1
        away_counts[away] += 1
        opponents[home].add(away)
        opponents[away].add(home)
        matchday_counts[f["matchday"]] += 1

    for t in ucl_team_names:
        assert home_counts[t] == 4, f"Team {t} should have exactly 4 home games, got {home_counts[t]}"
        assert away_counts[t] == 4, f"Team {t} should have exactly 4 away games, got {away_counts[t]}"
        assert len(opponents[t]) == 8, f"Team {t} should play 8 distinct opponents, got {len(opponents[t])}"

    for md in range(1, 9):
        assert matchday_counts[md] == 18, f"Matchday {md} must have 18 matches, got {matchday_counts[md]}"

    # 3. UEL Invariants (36 teams, 8 matchdays, 18 matches/matchday = 144 fixtures)
    uel = data["UEFA Europa League"]
    assert len(uel["teams"]) == 36, "UEL must have exactly 36 teams"
    uel_league = [f for f in uel["fixtures"] if f.get("stage") == "League Phase"]
    assert len(uel_league) == 144, f"UEL must have exactly 144 League Phase fixtures, got {len(uel_league)}"

    # 4. UECL Invariants (36 teams, 6 matchdays, 18 matches/matchday = 108 fixtures)
    uecl = data["UEFA Conference League"]
    assert len(uecl["teams"]) == 36, "UECL must have exactly 36 teams"
    uecl_league = [f for f in uecl["fixtures"] if f.get("stage") == "League Phase"]
    assert len(uecl_league) == 108, f"UECL must have exactly 108 League Phase fixtures, got {len(uecl_league)}"

    # 5. Knockout stages exist
    for comp_name in expected_comps:
        comp_data = data[comp_name]
        ko_stages = {f.get("stage") for f in comp_data["fixtures"] if f.get("stage") != "League Phase"}
        assert "Play-offs" in ko_stages or "Round of 16" in ko_stages, f"Knockout stages missing for {comp_name}"


def test_seed_european_cups_with_full_draw(db_session):
    """
    Tests seeding the complete verified European competition dataset into the database.
    """
    results = seed_european_cups(db_session)
    assert "UEFA Champions League" in results
    assert "UEFA Europa League" in results
    assert "UEFA Conference League" in results

    # Verify database contents
    ucl_comp = db_session.query(Competition).filter(Competition.name == "UEFA Champions League").first()
    assert ucl_comp is not None

    ucl_tourney = db_session.query(Tournament).filter(
        Tournament.competition_id == ucl_comp.id,
        Tournament.season_name == "2026/27"
    ).first()
    assert ucl_tourney is not None

    fixtures = db_session.query(Fixture).filter(Fixture.tournament_id == ucl_tourney.id).all()
    league_fixtures = [f for f in fixtures if f.stage == "League Phase"]
    assert len(league_fixtures) == 144
    assert len(fixtures) == 189
