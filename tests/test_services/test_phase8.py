from datetime import datetime
from backend.database import Team, Fixture, Competition, Tournament, TournamentTeam, FixtureDependency
from backend.services.tournament import propagate_knockout_fixtures, evaluate_nations_league_promotions, calculate_standings
from backend.crud.team import get_teams_by_group

def test_two_legged_tie_propagation(db_session):
    # Setup Cup Competition and Tournament
    comp = Competition(name="Copa del Rey", type="Cup", format_engine="cup")
    db_session.add(comp)
    db_session.flush()
    tourney = Tournament(competition_id=comp.id, season_name="2025/26")
    db_session.add(tourney)
    db_session.flush()

    # Teams
    t1 = Team(name="Real Madrid", elo=1900)
    t2 = Team(name="Barcelona", elo=1880)
    t3 = Team(name="Atletico Madrid", elo=1800)
    db_session.add_all([t1, t2, t3])
    db_session.flush()

    # Two-legged fixtures (Semi-final)
    # Leg 1: Barcelona (Home) vs Real Madrid (Away)
    f_leg1 = Fixture(
        tournament_id=tourney.id,
        home_team_id=t2.id,
        away_team_id=t1.id,
        stage="Semi-final",
        status="Finished",
        home_score=2,
        away_score=1,
        leg_number=1,
        date_utc=datetime.fromisoformat("2026-02-01T20:00:00")
    )
    # Leg 2: Real Madrid (Home) vs Barcelona (Away)
    f_leg2 = Fixture(
        tournament_id=tourney.id,
        home_team_id=t1.id,
        away_team_id=t2.id,
        stage="Semi-final",
        status="Finished",
        home_score=3,
        away_score=1,
        leg_number=2,
        date_utc=datetime.fromisoformat("2026-02-08T20:00:00")
    )
    # Final placeholder fixture
    f_final = Fixture(
        tournament_id=tourney.id,
        home_team_placeholder="Winner SF",
        stage="Final",
        status="Scheduled",
        date_utc=datetime.fromisoformat("2026-05-01T20:00:00")
    )
    db_session.add_all([f_leg1, f_leg2, f_final])
    db_session.flush()

    # Fixture dependency
    dep = FixtureDependency(
        source_fixture_id=f_leg2.id,
        target_fixture_id=f_final.id,
        slot="home",
        result_type="winner"
    )
    db_session.add(dep)
    db_session.commit()

    # Barcelona won leg 1: 2-1
    # Real Madrid won leg 2: 3-1
    # Aggregate score: Real Madrid 4 - 3 Barcelona. Real Madrid should propagate!
    propagate_knockout_fixtures(db_session)
    db_session.commit()
    
    # Reload final fixture
    db_session.refresh(f_final)
    assert f_final.home_team_id == t1.id  # Real Madrid

def test_nations_league_promotion_relegation(db_session):
    # Setup Nations League
    comp = Competition(name="UEFA Nations League", type="International", format_engine="nations_league")
    db_session.add(comp)
    db_session.flush()
    tourney = Tournament(competition_id=comp.id, season_name="2026/27", status="Active")
    db_session.add(tourney)
    db_session.flush()

    # Teams in League B Group 1
    teams = [
        Team(name="England", elo=1850),
        Team(name="Greece", elo=1700),
        Team(name="Ireland", elo=1600),
        Team(name="Finland", elo=1550)
    ]
    db_session.add_all(teams)
    db_session.flush()

    # Seed TournamentTeams with Division and Group
    tts = []
    for t in teams:
        tt = TournamentTeam(
            tournament_id=tourney.id,
            team_id=t.id,
            division="B",
            group_name="1"
        )
        tts.append(tt)
    db_session.add_all(tts)
    db_session.flush()

    # We also verify crud_team get_teams_by_group
    group_teams = get_teams_by_group(db_session, "B1", tournament_id=tourney.id)
    assert len(group_teams) == 4
    assert any(gt.name == "England" for gt in group_teams)

    # Let's seed completed matches so standings determine promotion/relegation
    # England wins all matches, Greece is 2nd, Ireland is 3rd, Finland loses all
    fixtures = []
    
    # England vs Finland
    fixtures.append(Fixture(
        tournament_id=tourney.id, home_team_id=teams[0].id, away_team_id=teams[3].id,
        stage="Group Stage", status="Finished", home_score=4, away_score=0, date_utc=datetime.now()
    ))
    # Finland vs England
    fixtures.append(Fixture(
        tournament_id=tourney.id, home_team_id=teams[3].id, away_team_id=teams[0].id,
        stage="Group Stage", status="Finished", home_score=0, away_score=3, date_utc=datetime.now()
    ))
    # Greece vs Ireland
    fixtures.append(Fixture(
        tournament_id=tourney.id, home_team_id=teams[1].id, away_team_id=teams[2].id,
        stage="Group Stage", status="Finished", home_score=2, away_score=1, date_utc=datetime.now()
    ))
    # Ireland vs Greece
    fixtures.append(Fixture(
        tournament_id=tourney.id, home_team_id=teams[2].id, away_team_id=teams[1].id,
        stage="Group Stage", status="Finished", home_score=1, away_score=1, date_utc=datetime.now()
    ))
    # England vs Greece
    fixtures.append(Fixture(
        tournament_id=tourney.id, home_team_id=teams[0].id, away_team_id=teams[1].id,
        stage="Group Stage", status="Finished", home_score=2, away_score=0, date_utc=datetime.now()
    ))
    # Greece vs England
    fixtures.append(Fixture(
        tournament_id=tourney.id, home_team_id=teams[1].id, away_team_id=teams[0].id,
        stage="Group Stage", status="Finished", home_score=1, away_score=2, date_utc=datetime.now()
    ))
    # England vs Ireland
    fixtures.append(Fixture(
        tournament_id=tourney.id, home_team_id=teams[0].id, away_team_id=teams[2].id,
        stage="Group Stage", status="Finished", home_score=3, away_score=1, date_utc=datetime.now()
    ))
    # Ireland vs England
    fixtures.append(Fixture(
        tournament_id=tourney.id, home_team_id=teams[2].id, away_team_id=teams[0].id,
        stage="Group Stage", status="Finished", home_score=0, away_score=1, date_utc=datetime.now()
    ))
    # Greece vs Finland
    fixtures.append(Fixture(
        tournament_id=tourney.id, home_team_id=teams[1].id, away_team_id=teams[3].id,
        stage="Group Stage", status="Finished", home_score=2, away_score=0, date_utc=datetime.now()
    ))
    # Finland vs Greece
    fixtures.append(Fixture(
        tournament_id=tourney.id, home_team_id=teams[3].id, away_team_id=teams[1].id,
        stage="Group Stage", status="Finished", home_score=0, away_score=2, date_utc=datetime.now()
    ))
    # Ireland vs Finland
    fixtures.append(Fixture(
        tournament_id=tourney.id, home_team_id=teams[2].id, away_team_id=teams[3].id,
        stage="Group Stage", status="Finished", home_score=1, away_score=0, date_utc=datetime.now()
    ))
    # Finland vs Ireland
    fixtures.append(Fixture(
        tournament_id=tourney.id, home_team_id=teams[3].id, away_team_id=teams[2].id,
        stage="Group Stage", status="Finished", home_score=1, away_score=2, date_utc=datetime.now()
    ))
    
    db_session.add_all(fixtures)
    db_session.commit()

    # Check calculate_standings
    standings = calculate_standings(db_session, "B1", tournament_id=tourney.id)
    assert len(standings) == 4
    assert standings[0]["name"] == "England"
    assert standings[3]["name"] == "Finland"

    # Evaluate promotion/relegation
    evaluate_nations_league_promotions(db_session, tourney.id)
    
    # Reload tournament teams
    db_session.expire_all()
    tt_england = db_session.query(TournamentTeam).filter(TournamentTeam.team_id == teams[0].id).first()
    tt_finland = db_session.query(TournamentTeam).filter(TournamentTeam.team_id == teams[3].id).first()
    tt_greece = db_session.query(TournamentTeam).filter(TournamentTeam.team_id == teams[1].id).first()
    
    assert tt_england.promoted == True
    assert tt_england.relegated == False
    assert tt_finland.relegated == True
    assert tt_finland.promoted == False
    assert tt_greece.promoted == False
    assert tt_greece.relegated == False
