from backend.services.weights import normalize_weights

def test_normalize_weights_standard():
    weights = {"elo": 0.5, "odds": 0.3, "form": 0.2, "narrative": 0.0}
    normalized = normalize_weights(weights)
    assert sum(normalized.values()) == 1.0
    assert normalized["elo"] == 0.5
    assert normalized["odds"] == 0.3
    assert normalized["form"] == 0.2
    assert normalized["narrative"] == 0.0

def test_normalize_weights_all_zero():
    weights = {"elo": 0.0, "odds": 0.0, "form": 0.0, "narrative": 0.0}
    normalized = normalize_weights(weights)
    assert sum(normalized.values()) == 1.0
    assert normalized["elo"] == 0.25
    assert normalized["odds"] == 0.25
    assert normalized["form"] == 0.25
    assert normalized["narrative"] == 0.25

def test_normalize_weights_non_normalized():
    weights = {"elo": 1.0, "odds": 1.0, "form": 1.0, "narrative": 1.0}
    normalized = normalize_weights(weights)
    assert sum(normalized.values()) == 1.0
    assert normalized["elo"] == 0.25


from unittest.mock import patch
from backend.scoring import calculate_watchability
from backend.database import Team, Fixture, Competition, Tournament, TournamentTeam, FixtureOdds
from datetime import datetime

def test_calculate_watchability_dynamic_stakes(db_session):
    comp = Competition(name="World Cup Test", type="International")
    db_session.add(comp)
    db_session.flush()
    tourney = Tournament(competition_id=comp.id, season_name="2026")
    db_session.add(tourney)
    db_session.flush()
    
    t1 = Team(name="TeamA", elo=1600, form_score=50.0, win_streak=0)
    t2 = Team(name="TeamB", elo=1600, form_score=50.0, win_streak=0)
    db_session.add_all([t1, t2])
    db_session.flush()
    
    tt1 = TournamentTeam(tournament_id=tourney.id, team_id=t1.id, group_name="A")
    tt2 = TournamentTeam(tournament_id=tourney.id, team_id=t2.id, group_name="A")
    db_session.add_all([tt1, tt2])
    db_session.flush()
    
    f = Fixture(
        tournament_id=tourney.id,
        home_team_id=t1.id,
        away_team_id=t2.id,
        stage="Group Stage",
        status="Scheduled",
        date_utc=datetime.now()
    )
    odds = FixtureOdds(
        fixture_id=f.id,
        recorded_at=datetime.now(),
        odds_home=2.5,
        odds_draw=3.2,
        odds_away=2.8
    )
    f.odds_history.append(odds)
    db_session.add(f)
    db_session.commit()
    
    # 1. Test fallback when no simulation probabilities are available (should be 50.0 each)
    with patch("backend.scoring.get_simulation_probabilities") as mock_get_probs:
        mock_get_probs.return_value = {}
        res = calculate_watchability(f, t1, t2, db_session)
        assert res["narrative_score"] == 100.0
        assert any("Crucial World Cup Group A clash" in r for r in res["reasons"])

    # 2. Test high stakes decider: both teams at 50%
    with patch("backend.scoring.get_simulation_probabilities") as mock_get_probs:
        mock_get_probs.return_value = {"TeamA": 50.0, "TeamB": 50.0}
        res = calculate_watchability(f, t1, t2, db_session)
        assert res["narrative_score"] == 100.0
        assert any("High stakes decider" in r for r in res["reasons"])
        
    # 3. Test dead rubber: both teams qualified (100% chance)
    with patch("backend.scoring.get_simulation_probabilities") as mock_get_probs:
        mock_get_probs.return_value = {"TeamA": 100.0, "TeamB": 100.0}
        res = calculate_watchability(f, t1, t2, db_session)
        assert res["narrative_score"] == 10.0
        assert any("Qualification settled" in r for r in res["reasons"])

    # 4. Test mixed stakes: one team qualified, one eliminated
    with patch("backend.scoring.get_simulation_probabilities") as mock_get_probs:
        mock_get_probs.return_value = {"TeamA": 100.0, "TeamB": 0.0}
        res = calculate_watchability(f, t1, t2, db_session)
        assert res["narrative_score"] == 10.0
        assert any("Mixed stakes" in r for r in res["reasons"])

