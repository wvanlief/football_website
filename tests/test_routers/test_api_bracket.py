from datetime import datetime

from backend.database import Competition, Tournament, Team, TournamentTeam, Fixture


def test_bracket_for_league_phase_cup_is_not_world_cup_tree(client, db_session):
    wc = Competition(name="FIFA World Cup Bracket Test", type="International", format_engine="group_knockout")
    ucl = Competition(name="UEFA Champions League Bracket Test", type="Cup", format_engine="league_phase_knockout")
    db_session.add_all([wc, ucl])
    db_session.flush()

    wc_tourney = Tournament(competition_id=wc.id, season_name="2026", status="Active")
    ucl_tourney = Tournament(competition_id=ucl.id, season_name="2026/27", status="Active")
    db_session.add_all([wc_tourney, ucl_tourney])
    db_session.flush()

    home = Team(name="Bracket Home", elo=1900)
    away = Team(name="Bracket Away", elo=1850)
    db_session.add_all([home, away])
    db_session.flush()
    db_session.add(TournamentTeam(tournament_id=ucl_tourney.id, team_id=home.id))
    db_session.add(TournamentTeam(tournament_id=ucl_tourney.id, team_id=away.id))
    db_session.add(Fixture(
        tournament_id=ucl_tourney.id,
        home_team_id=home.id,
        away_team_id=away.id,
        stage="Round of 16",
        status="Scheduled",
        date_utc=datetime(2027, 3, 10),
    ))
    db_session.add(Fixture(
        tournament_id=ucl_tourney.id,
        home_team_id=home.id,
        away_team_id=away.id,
        stage="3rd Qualifying Round",
        status="Finished",
        home_score=2,
        away_score=1,
        date_utc=datetime(2026, 8, 12),
    ))
    db_session.commit()

    response = client.get(f"/api/bracket?tournament_id={ucl_tourney.id}")
    assert response.status_code == 200
    payload = response.json()
    bracket = payload["bracket"]
    assert len(bracket["r16"]) == 1
    assert bracket["r16"][0]["team1"]["name"] == "Bracket Home"
    assert all(match.get("stage") != "3rd Qualifying Round" for match in bracket["r16"])
    assert bracket["r32"] == []
    assert "champion" in bracket
