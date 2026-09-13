"""Frontend gates that prevent stale / cross-competition rows on the homepage."""
from pathlib import Path

APP_JS = Path("frontend/js/app.js").read_text(encoding="utf-8")


def test_process_hydrated_fixtures_gates_past_calendar_dates():
    assert "if (matchDateStr >= todayStr)" in APP_JS
    assert 'if (fdata.status === "Finished")' in APP_JS
    assert "finishedFixtures.push(fdata)" in APP_JS


def test_homepage_competition_filter_matches_competition_name():
    assert "return match.competition_name === activeCompFilter;" in APP_JS
    assert "const filteredToday = activeFixtures.today.filter(filterFn);" in APP_JS
    assert "const filteredTomorrow = activeFixtures.tomorrow.filter(filterFn);" in APP_JS
    assert "const filteredWeek = activeFixtures.this_week.filter(filterFn);" in APP_JS
