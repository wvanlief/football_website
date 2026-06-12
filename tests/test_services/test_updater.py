from datetime import datetime, timezone
from unittest.mock import patch, MagicMock
from backend.database import Team, Fixture, Competition, Tournament, TournamentTeam, FixtureOdds, EloHistory
from backend.services.updater import update_results_and_odds

def test_update_results_and_odds(db_session):
    # 1. Setup base competition and tournament
    comp = Competition(name="FIFA World Cup", type="International")
    db_session.add(comp)
    db_session.flush()
    
    tourney = Tournament(competition_id=comp.id, season_name="2026", status="Active")
    db_session.add(tourney)
    db_session.flush()
    
    # 2. Setup teams
    t1 = Team(name="Spain", elo=2000, form_score=75.0, win_streak=1, draw_streak=0, loss_streak=0)
    t2 = Team(name="Germany", elo=1900, form_score=70.0, win_streak=0, draw_streak=0, loss_streak=0)
    db_session.add_all([t1, t2])
    db_session.flush()
    
    # 3. Associate teams to tournament
    tt1 = TournamentTeam(tournament_id=tourney.id, team_id=t1.id, group_name="H")
    tt2 = TournamentTeam(tournament_id=tourney.id, team_id=t2.id, group_name="E")
    db_session.add_all([tt1, tt2])
    db_session.flush()
    
    # 4. Create an existing scheduled group fixture
    f1 = Fixture(
        tournament_id=tourney.id,
        home_team_id=t1.id,
        away_team_id=t2.id,
        stage="Group Stage",
        status="Scheduled",
        date_utc=datetime(2026, 6, 11, 13, 0, tzinfo=timezone.utc),
        winner_id=None
    )
    db_session.add(f1)
    db_session.flush()
    
    # Initial odds for f1
    init_odds = FixtureOdds(
        fixture_id=f1.id,
        recorded_at=datetime(2026, 6, 9, 13, 0, tzinfo=timezone.utc),
        odds_home=1.8,
        odds_draw=3.4,
        odds_away=4.2
    )
    db_session.add(init_odds)
    db_session.commit()
    
    # Mocks representing the GitHub JSON responses
    mock_teams = [
        {"id": "1", "name_en": "Spain", "groups": "H"},
        {"id": "2", "name_en": "Germany", "groups": "E"}
    ]
    mock_matches = [
        {
            "id": "1",
            "home_team_id": "1",
            "away_team_id": "2",
            "home_score": "2",
            "away_score": "1",
            "finished": "TRUE",
            "local_date": "06/11/2026 13:00",
            "stadium_id": "1",
            "type": "group"
        },
        {
            "id": "2",
            "home_team_id": "1",
            "away_team_id": "2",
            "home_score": "0",
            "away_score": "0",
            "finished": "FALSE",
            "local_date": "06/20/2026 15:00",
            "stadium_id": "5",
            "type": "round_of_32"
        }
    ]
    
    with patch("backend.services.updater.fetch_json") as mock_fetch, \
         patch("backend.services.updater.update_odds_from_api") as mock_odds_api, \
         patch("backend.services.updater.run_monte_carlo_simulation") as mock_sim:
         
        def fetch_side_effect(url):
            if "teams" in url:
                return {"teams": mock_teams}
            elif "games" in url or "matches" in url:
                return {"games": mock_matches}
            return []
            
        mock_fetch.side_effect = fetch_side_effect
        
        result = update_results_and_odds(db_session)
        
    # Verify execution return codes
    assert result["status"] == "success"
    assert result["fixtures_created"] == 1
    assert result["fixtures_updated_results"] == 1
    
    # Assert existing match transitioned to Finished
    db_session.refresh(f1)
    assert f1.status == "Finished"
    assert f1.home_score == 2
    assert f1.away_score == 1
    assert f1.winner_id == t1.id
    
    # Assert ELO calculation updated Spain (Winner) up and Germany (Loser) down
    db_session.refresh(t1)
    db_session.refresh(t2)
    assert t1.elo > 2000
    assert t2.elo < 1900
    
    # Assert streaks updated correctly
    assert t1.win_streak == 2
    assert t2.loss_streak == 1
    
    # Assert new knockout fixture created
    new_fixture = db_session.query(Fixture).filter(Fixture.stage == "Round of 32").first()
    assert new_fixture is not None
    assert new_fixture.home_team_id == t1.id
    assert new_fixture.away_team_id == t2.id
    assert new_fixture.status == "Scheduled"
    
    # Assert EloHistory logs were created
    history_spain = db_session.query(EloHistory).filter(EloHistory.team_id == t1.id).first()
    history_germany = db_session.query(EloHistory).filter(EloHistory.team_id == t2.id).first()
    assert history_spain is not None
    assert history_germany is not None
    assert history_spain.elo_rating == t1.elo
    assert history_germany.elo_rating == t2.elo
