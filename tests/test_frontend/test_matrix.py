from pathlib import Path

GROUP_JS = Path("frontend/js/group.js").read_text(encoding="utf-8")


def test_league_phase_matrix_mirrors_away_fixtures_into_row():
    assert "venue: 'A'" in GROUP_JS
    assert "fixtureMap[awayName] && !fixtureMap[awayName][homeName]" in GROUP_JS
    assert "Each fixture appears twice" in GROUP_JS
    assert "isAway ? `${homeTeam} @ ${awayTeam}`" in GROUP_JS
