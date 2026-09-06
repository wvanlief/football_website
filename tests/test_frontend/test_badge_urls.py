from pathlib import Path

GROUP_JS = Path("frontend/js/group.js").read_text(encoding="utf-8")
REC_JS = Path("frontend/js/recommended.js").read_text(encoding="utf-8")
SHARED_JS = Path("frontend/js/shared.js").read_text(encoding="utf-8")


def test_group_and_hot_list_pass_team_objects_to_get_flag_url():
    assert "getFlagUrl(match.home_team.name" not in GROUP_JS
    assert "getFlagUrl(match.away_team.name" not in GROUP_JS
    assert "getFlagUrl(match.home_team)" in GROUP_JS
    assert "getFlagUrl(match.home_team.name" not in REC_JS
    assert "getFlagUrl(match.home_team)" in REC_JS
    assert "media.api-sports.io/football/teams/" in SHARED_JS
