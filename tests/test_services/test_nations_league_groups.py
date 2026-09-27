from backend.scripts.stamp_nations_league_groups import (
    GROUPS,
    canonical_name,
    check_groups,
    group_by_team,
)

# Results and fixtures from 26–27 September 2026. Each pair is one group.
WEEKEND_PAIRS = (
    ("England", "Spain", "A3"),
    ("Czechia", "Croatia", "A3"),
    ("Serbia", "Netherlands", "A2"),
    ("Germany", "Greece", "A2"),
    ("Denmark", "Wales", "A4"),
    ("Norway", "Portugal", "A4"),
    ("Slovenia", "Scotland", "B1"),
    ("North Macedonia", "Switzerland", "B1"),
    ("Austria", "Kosovo", "B3"),
    ("Israel", "Republic of Ireland", "B3"),
    ("San Marino", "Finland", "C1"),
    ("Albania", "Belarus", "C1"),
    ("Faroe Islands", "Kazakhstan", "C3"),
    ("Slovakia", "Moldova", "C3"),
    ("Iceland", "Estonia", "C4"),
    ("Bulgaria", "Luxembourg", "C4"),
    ("Gibraltar", "Andorra", "D1"),
    ("Lithuania", "Azerbaijan", "D2"),
)


def test_draw_has_54_unique_teams_and_the_published_sizes():
    assigned = group_by_team()
    assert len(assigned) == 54
    sizes = {code: len(teams) for code, teams in GROUPS.items()}
    assert sizes == {
        "A1": 4, "A2": 4, "A3": 4, "A4": 4,
        "B1": 4, "B2": 4, "B3": 4, "B4": 4,
        "C1": 4, "C2": 4, "C3": 4, "C4": 4,
        "D1": 3, "D2": 3,
    }


def test_weekend_results_sit_in_the_draw_groups():
    assigned = group_by_team()
    for left, right, code in WEEKEND_PAIRS:
        assert assigned[canonical_name(left)] == (code[0], code[1:])
        assert assigned[canonical_name(right)] == (code[0], code[1:])


def test_highlightly_spellings_resolve_to_the_draw():
    assert canonical_name("Turkey") == "Türkiye"
    assert canonical_name("Czech Republic") == "Czechia"
    assert canonical_name("Ireland") == "Republic of Ireland"
    assert canonical_name("Northern Ireland") == "Northern Ireland"
    assert canonical_name("Bosnia & Herzegovina") == "Bosnia and Herzegovina"


def test_fixture_graph_must_match_one_group_exactly():
    names = []
    for teams in GROUPS.values():
        names.extend(teams)
    ids = {name: {index} for index, name in enumerate(names)}
    pairs = []
    for teams in GROUPS.values():
        for index, home in enumerate(teams):
            for away in teams[index + 1 :]:
                pairs.append((next(iter(ids[home])), next(iter(ids[away]))))
    assert check_groups(ids, pairs) == []

    # England playing France would glue A3 to A1.
    crossed = pairs + [(next(iter(ids["England"])), next(iter(ids["France"])))]
    problems = check_groups(ids, crossed)
    assert problems
    assert any("A1" in problem or "A3" in problem for problem in problems)


def test_two_rows_for_one_nation_still_match_their_group():
    names = []
    for teams in GROUPS.values():
        names.extend(teams)
    ids = {name: {index} for index, name in enumerate(names)}
    ireland_alias = 1000
    ids["Republic of Ireland"].add(ireland_alias)
    pairs = []
    for teams in GROUPS.values():
        for index, home in enumerate(teams):
            for away in teams[index + 1 :]:
                pairs.append((next(iter(ids[home])), next(iter(ids[away]))))
    # One Ireland match is stored on the alias row.
    pairs.append((ireland_alias, next(iter(ids["Austria"]))))
    assert check_groups(ids, pairs) == []
