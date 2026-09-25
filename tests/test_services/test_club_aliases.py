from datetime import datetime

from backend.database import Fixture, Team, Tournament, TournamentTeam, Competition
from backend.services.ingestion.normalizer import NameNormalizer, TEAM_NAME_ALIASES
from backend.services.ingestion.team_merge import merge_club_aliases
from backend.services.ingestion.team_resolver import TeamResolver


def test_club_draw_names_normalize_to_api_football_names():
    normalizer = NameNormalizer()
    assert normalizer.normalize("Club Brugge") == "Club Brugge KV"
    assert normalizer.normalize("Bayern Munich") == "Bayern München"
    assert normalizer.normalize("Paris Saint-Germain") == "Paris Saint Germain"
    assert normalizer.normalize("Inter Milan") == "Inter"
    assert normalizer.normalize("Young Boys") == "BSC Young Boys"
    assert normalizer.normalize("FC Salzburg") == "Red Bull Salzburg"
    assert normalizer.normalize("Crvena Zvezda") == "FK Crvena Zvezda"
    assert normalizer.normalize("Sparta Prague") == "Sparta Praha"
    assert normalizer.normalize("Brest") == "Stade Brestois 29"
    assert normalizer.normalize("Atlético de Madrid") == "Atlético Madrid"
    assert normalizer.normalize("Club Atlético de Madrid") == "Atlético Madrid"
    assert normalizer.normalize("Atletico Madrid") == "Atlético Madrid"
    assert normalizer.normalize("ŠK Slovan Bratislava") == "Slovan Bratislava"
    assert normalizer.normalize("Como 1907") == "Como"
    assert "Club Brugge" in TEAM_NAME_ALIASES
    assert "Como 1907" in TEAM_NAME_ALIASES


def test_laliga_football_data_names_resolve_to_catalog_clubs():
    normalizer = NameNormalizer()
    expected = {
        "Barça": "Barcelona",
        "Málaga CF": "Malaga",
        "Deportivo Alavés": "Alaves",
        "RC Celta de Vigo": "Celta Vigo",
        "RC Deportivo La Coruña": "Deportivo La Coruna",
        "Real Racing Club de Santander": "Racing Santander",
    }
    for raw, canonical in expected.items():
        assert normalizer.normalize(raw) == canonical
        assert TEAM_NAME_ALIASES[raw] == canonical


def test_laliga_aliases_resolve_onto_existing_clubs(db_session):
    barcelona = Team(name="Barcelona", team_type="Club", elo=1900)
    malaga = Team(name="Malaga", team_type="Club")
    db_session.add_all([barcelona, malaga])
    db_session.commit()

    resolver = TeamResolver()
    resolved = resolver.resolve(
        db_session,
        provider_name="football_data",
        raw_name="Barça",
        external_id="81",
        team_type="Club",
    )
    assert resolved.id == barcelona.id
    assert db_session.query(Team).filter(Team.name == "Barça").first() is None
    assert resolver.resolve(
        db_session,
        provider_name="football_data",
        raw_name="Málaga CF",
        external_id="84",
        team_type="Club",
    ).id == malaga.id


def test_merge_club_aliases_rewires_fixtures(db_session):
    canonical = Team(name="Club Brugge KV", api_id=569, elo=1500, team_type="Club", logo_url="/static/badges/569.png")
    orphan = Team(name="Club Brugge", api_id=None, elo=1710, team_type="Club")
    db_session.add_all([canonical, orphan])
    db_session.flush()

    comp = Competition(name="UCL Merge Test", type="Cup", format_engine="league_phase_knockout")
    db_session.add(comp)
    db_session.flush()
    tourney = Tournament(competition_id=comp.id, season_name="2026/27", status="Active")
    db_session.add(tourney)
    db_session.flush()
    db_session.add(TournamentTeam(tournament_id=tourney.id, team_id=orphan.id))
    opponent = Team(name="Merge Opponent", api_id=42, elo=1900, team_type="Club")
    db_session.add(opponent)
    db_session.flush()
    db_session.add(TournamentTeam(tournament_id=tourney.id, team_id=opponent.id))
    db_session.add(Fixture(
        tournament_id=tourney.id,
        home_team_id=orphan.id,
        away_team_id=opponent.id,
        stage="League Phase",
        status="Scheduled",
        date_utc=datetime(2026, 9, 16),
    ))
    db_session.commit()

    logs = merge_club_aliases(db_session)
    assert any("Club Brugge" in line and "Club Brugge KV" in line for line in logs)

    assert db_session.query(Team).filter(Team.name == "Club Brugge").first() is None
    kv = db_session.query(Team).filter(Team.name == "Club Brugge KV").one()
    assert kv.api_id == 569
    assert kv.elo == 1710
    fixture = db_session.query(Fixture).one()
    assert fixture.home_team_id == kv.id
    tt = db_session.query(TournamentTeam).filter(TournamentTeam.team_id == kv.id).one()
    assert tt.tournament_id == tourney.id
