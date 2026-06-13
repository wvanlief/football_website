from datetime import datetime, timezone
from backend.database import Fixture, Competition, Tournament, Team, TournamentTeam

def test_get_fixtures_empty(client):
    response = client.get("/api/fixtures")
    assert response.status_code == 200
    data = response.json()
    assert "today" in data
    assert "tomorrow" in data
    assert "this_week" in data
    assert len(data["today"]) == 0

def test_get_fixtures_with_data(client, db_session):
    # Populate competition and tournament
    comp = Competition(name="World Cup", type="International")
    db_session.add(comp)
    db_session.flush()
    tourney = Tournament(competition_id=comp.id, season_name="2026")
    db_session.add(tourney)
    db_session.flush()

    # Populate teams and their tournament settings
    team1 = Team(name="Germany", elo=1900)
    team2 = Team(name="Scotland", elo=1650)
    db_session.add_all([team1, team2])
    db_session.flush()

    tt1 = TournamentTeam(tournament_id=tourney.id, team_id=team1.id, group_name="A")
    tt2 = TournamentTeam(tournament_id=tourney.id, team_id=team2.id, group_name="A")
    db_session.add_all([tt1, tt2])
    db_session.flush()
    
    # Use the current UTC date dynamically
    today_utc = datetime.now(timezone.utc)
    
    fixture = Fixture(
        tournament_id=tourney.id,
        home_team_id=team1.id,
        away_team_id=team2.id,
        date_utc=today_utc.replace(hour=20, minute=0, second=0, microsecond=0, tzinfo=None),
        stage="Group Stage",
        status="Scheduled"
    )
    db_session.add(fixture)
    db_session.commit()
    
    response = client.get("/api/fixtures")
    assert response.status_code == 200
    data = response.json()
    assert len(data["today"]) == 1
    assert data["today"][0]["home_team"]["name"] == "Germany"
    assert data["today"][0]["away_team"]["name"] == "Scotland"


def test_get_fixtures_sorting(client, db_session):
    # Setup database with multiple fixtures to test sorting
    comp = Competition(name="World Cup Sorting", type="International")
    db_session.add(comp)
    db_session.flush()
    tourney = Tournament(competition_id=comp.id, season_name="2026")
    db_session.add(tourney)
    db_session.flush()

    t1 = Team(name="Germany Sort", elo=1900)
    t2 = Team(name="Scotland Sort", elo=1650)
    t3 = Team(name="France Sort", elo=2000)
    db_session.add_all([t1, t2, t3])
    db_session.flush()

    tt1 = TournamentTeam(tournament_id=tourney.id, team_id=t1.id, group_name="A")
    tt2 = TournamentTeam(tournament_id=tourney.id, team_id=t2.id, group_name="A")
    tt3 = TournamentTeam(tournament_id=tourney.id, team_id=t3.id, group_name="A")
    db_session.add_all([tt1, tt2, tt3])
    db_session.flush()

    today_utc = datetime.now(timezone.utc)

    # Fixture 1: 20:00 UTC, high watchability
    f1 = Fixture(
        tournament_id=tourney.id,
        home_team_id=t1.id,
        away_team_id=t2.id,
        date_utc=today_utc.replace(hour=20, minute=0, second=0, microsecond=0, tzinfo=None),
        stage="Group Stage",
        status="Scheduled",
        watchability_score=90.0
    )
    # Fixture 2: 16:00 UTC, low watchability
    f2 = Fixture(
        tournament_id=tourney.id,
        home_team_id=t2.id,
        away_team_id=t3.id,
        date_utc=today_utc.replace(hour=16, minute=0, second=0, microsecond=0, tzinfo=None),
        stage="Group Stage",
        status="Scheduled",
        watchability_score=40.0
    )
    # Fixture 3: 18:00 UTC, medium watchability
    f3 = Fixture(
        tournament_id=tourney.id,
        home_team_id=t3.id,
        away_team_id=t1.id,
        date_utc=today_utc.replace(hour=18, minute=0, second=0, microsecond=0, tzinfo=None),
        stage="Group Stage",
        status="Scheduled",
        watchability_score=70.0
    )
    db_session.add_all([f1, f2, f3])
    db_session.commit()

    response = client.get("/api/fixtures")
    assert response.status_code == 200
    data = response.json()
    
    # We want ascending time: 16:00, then 18:00, then 20:00
    assert len(data["today"]) == 3
    assert data["today"][0]["home_team"]["name"] == "Scotland Sort"  # 16:00
    assert data["today"][1]["home_team"]["name"] == "France Sort"    # 18:00
    assert data["today"][2]["home_team"]["name"] == "Germany Sort"   # 20:00


def test_get_calendar_fixtures(client, db_session):
    from datetime import timedelta
    comp = Competition(name="World Cup Calendar", type="International")
    db_session.add(comp)
    db_session.flush()
    tourney = Tournament(competition_id=comp.id, season_name="2026")
    db_session.add(tourney)
    db_session.flush()

    t1 = Team(name="Germany Cal", elo=1900)
    t2 = Team(name="Scotland Cal", elo=1650)
    db_session.add_all([t1, t2])
    db_session.flush()

    tt1 = TournamentTeam(tournament_id=tourney.id, team_id=t1.id, group_name="A")
    tt2 = TournamentTeam(tournament_id=tourney.id, team_id=t2.id, group_name="A")
    db_session.add_all([tt1, tt2])
    db_session.flush()

    today_utc = datetime.now(timezone.utc)

    # Fixture 1: 5 days ago (should be in calendar since 5 < 7)
    f1 = Fixture(
        tournament_id=tourney.id,
        home_team_id=t1.id,
        away_team_id=t2.id,
        date_utc=(today_utc - timedelta(days=5)).replace(tzinfo=None),
        stage="Group Stage",
        status="Finished",
        home_score=2,
        away_score=1,
        watchability_score=80.0
    )
    # Fixture 2: 15 days from now (should be in calendar since 15 < 30)
    f2 = Fixture(
        tournament_id=tourney.id,
        home_team_id=t2.id,
        away_team_id=t1.id,
        date_utc=(today_utc + timedelta(days=15)).replace(tzinfo=None),
        stage="Group Stage",
        status="Scheduled",
        watchability_score=60.0
    )
    # Fixture 3: 40 days from now (should NOT be in calendar since 40 > 30)
    f3 = Fixture(
        tournament_id=tourney.id,
        home_team_id=t1.id,
        away_team_id=t2.id,
        date_utc=(today_utc + timedelta(days=40)).replace(tzinfo=None),
        stage="Group Stage",
        status="Scheduled",
        watchability_score=75.0
    )
    db_session.add_all([f1, f2, f3])
    db_session.commit()

    response = client.get("/api/fixtures/calendar")
    assert response.status_code == 200
    data = response.json()
    
    # Check that we only get f1 and f2, and their schemas are minimal
    assert len(data) == 2
    
    # Ensure items are sorted by date
    assert data[0]["id"] == f1.id
    assert data[1]["id"] == f2.id
    
    # Check minimal schema fields
    assert "home_team" in data[0]
    assert "name" in data[0]["home_team"]
    assert "elo" not in data[0]["home_team"]  # Optimized size!
    assert "players" not in data[0]["home_team"]  # Optimized size!
    assert data[0]["home_team"]["name"] == "Germany Cal"
    assert data[0]["score"] == "2 - 1"
    assert data[0]["watchability_score"] == 80.0
    
    assert data[1]["home_team"]["name"] == "Scotland Cal"
    assert data[1]["score"] is None
    assert data[1]["watchability_score"] == 60.0


def test_get_fixture_detail(client, db_session):
    comp = Competition(name="World Cup Detail", type="International")
    db_session.add(comp)
    db_session.flush()
    tourney = Tournament(competition_id=comp.id, season_name="2026")
    db_session.add(tourney)
    db_session.flush()

    t1 = Team(name="Germany Det", elo=1900)
    t2 = Team(name="Scotland Det", elo=1650)
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
        date_utc=datetime.now(timezone.utc).replace(tzinfo=None),
        stage="Group Stage",
        status="Scheduled",
        watchability_score=85.0
    )
    db_session.add(f)
    db_session.commit()

    # Success case
    response = client.get(f"/api/fixtures/{f.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == f.id
    assert data["home_team"]["name"] == "Germany Det"
    assert "elo" in data["home_team"]  # Full schema!
    assert "watchability" in data
    assert data["watchability"]["overall"] == 85.0

    # 404 case
    response404 = client.get("/api/fixtures/999999")
    assert response404.status_code == 404



