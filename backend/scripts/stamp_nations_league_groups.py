"""Stamp UEFA Nations League division and group onto tournament_teams.

Groups are the 2026/27 league-phase draw (UEFA, 12 February 2026). Before
writing, every fixture component in the tournament must match exactly one
of those groups. A mismatch aborts with no update.

    python -m backend.scripts.stamp_nations_league_groups
    python -m backend.scripts.stamp_nations_league_groups --execute
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.database import Competition, Fixture, SessionLocal, Team, Tournament, TournamentTeam
from backend.services.ingestion.normalizer import NameNormalizer

# League letter + group number -> teams. Spelling is the draw name.
GROUPS: dict[str, tuple[str, ...]] = {
    "A1": ("France", "Italy", "Belgium", "Türkiye"),
    "A2": ("Germany", "Netherlands", "Serbia", "Greece"),
    "A3": ("Spain", "Croatia", "England", "Czechia"),
    "A4": ("Portugal", "Denmark", "Norway", "Wales"),
    "B1": ("Scotland", "Switzerland", "Slovenia", "North Macedonia"),
    "B2": ("Hungary", "Ukraine", "Georgia", "Northern Ireland"),
    "B3": ("Israel", "Austria", "Republic of Ireland", "Kosovo"),
    "B4": ("Poland", "Bosnia and Herzegovina", "Romania", "Sweden"),
    "C1": ("Albania", "Finland", "Belarus", "San Marino"),
    "C2": ("Montenegro", "Armenia", "Cyprus", "Latvia"),
    "C3": ("Kazakhstan", "Slovakia", "Faroe Islands", "Moldova"),
    "C4": ("Iceland", "Bulgaria", "Estonia", "Luxembourg"),
    "D1": ("Gibraltar", "Malta", "Andorra"),
    "D2": ("Lithuania", "Azerbaijan", "Liechtenstein"),
}

# Highlightly / catalog spellings that are not already in TEAM_NAME_ALIASES.
_EXTRA_ALIASES = {
    "turkey": "Türkiye",
    "turkiye": "Türkiye",
    "türkiye": "Türkiye",
    "czech republic": "Czechia",
    "czechia": "Czechia",
    "republic of ireland": "Republic of Ireland",
    "ireland": "Republic of Ireland",
    "bosnia and herzegovina": "Bosnia and Herzegovina",
    "bosnia-herzegovina": "Bosnia and Herzegovina",
    "north macedonia": "North Macedonia",
    "fyrom": "North Macedonia",
    "macedonia": "North Macedonia",
}


def canonical_name(raw: str) -> str:
    cleaned = NameNormalizer().normalize(raw or "").strip()
    return _EXTRA_ALIASES.get(cleaned.casefold(), cleaned)


def group_by_team() -> dict[str, tuple[str, str]]:
    """Map a canonical team name to (division, group_number)."""
    assigned: dict[str, tuple[str, str]] = {}
    for code, teams in GROUPS.items():
        division, number = code[0], code[1:]
        for team in teams:
            key = canonical_name(team)
            if key in assigned:
                raise ValueError(f"{key} is listed in more than one group")
            assigned[key] = (division, number)
    return assigned


def fixture_components(pairs: list[tuple[int, int]]) -> list[set[int]]:
    parent: dict[int, int] = {}

    def find(node: int) -> int:
        parent.setdefault(node, node)
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    def union(left: int, right: int) -> None:
        a, b = find(left), find(right)
        if a != b:
            parent[b] = a

    for home_id, away_id in pairs:
        union(home_id, away_id)
    buckets: dict[int, set[int]] = {}
    for node in parent:
        buckets.setdefault(find(node), set()).add(node)
    return list(buckets.values())


def check_groups(
    team_ids_by_canonical: dict[str, int],
    pairs: list[tuple[int, int]],
) -> list[str]:
    """Return human-readable problems. Empty means the draw matches the fixtures."""
    problems: list[str] = []
    official = group_by_team()
    known_ids = set(team_ids_by_canonical.values())
    components = fixture_components([(h, a) for h, a in pairs if h in known_ids and a in known_ids])
    id_to_name = {team_id: name for name, team_id in team_ids_by_canonical.items()}

    seen_codes: set[str] = set()
    for component in components:
        codes = set()
        for team_id in component:
            label = official.get(id_to_name[team_id])
            if label is None:
                problems.append(f"Team id {team_id} has no draw group")
                continue
            codes.add(f"{label[0]}{label[1]}")
        if len(codes) != 1:
            names = sorted(id_to_name[team_id] for team_id in component)
            problems.append(f"Fixture group {names} maps to {sorted(codes) or 'nothing'}")
            continue
        code = next(iter(codes))
        seen_codes.add(code)
        expected_ids = {team_ids_by_canonical[canonical_name(name)] for name in GROUPS[code]}
        if component != expected_ids:
            problems.append(f"{code} fixtures {sorted(component)} != draw {sorted(expected_ids)}")

    missing_codes = set(GROUPS) - seen_codes
    if missing_codes:
        problems.append(f"No fixtures for {sorted(missing_codes)}")
    return problems


def _tournament(db):
    return (
        db.query(Tournament)
        .join(Competition)
        .filter(
            Competition.name == "UEFA Nations League",
            Tournament.season_name == "2026/27",
        )
        .one_or_none()
    )


def stamp(db, execute: bool) -> int:
    tourney = _tournament(db)
    if tourney is None:
        print("UEFA Nations League 2026/27 tournament not found.")
        return 1

    rows = (
        db.query(TournamentTeam, Team)
        .join(Team, Team.id == TournamentTeam.team_id)
        .filter(TournamentTeam.tournament_id == tourney.id)
        .all()
    )
    official = group_by_team()
    team_ids_by_canonical: dict[str, int] = {}
    unresolved: list[str] = []
    for tt, team in rows:
        name = canonical_name(team.name)
        if name not in official:
            unresolved.append(team.name)
            continue
        if name in team_ids_by_canonical:
            print(f"Duplicate team row for {name}: {team.name}")
            return 1
        team_ids_by_canonical[name] = team.id

    if unresolved:
        print("These tournament teams are not in the 2026/27 draw:")
        for name in sorted(unresolved):
            print(f"  {name}")
        return 1

    missing = sorted(set(official) - set(team_ids_by_canonical))
    if missing:
        print("Draw teams missing from the tournament:")
        for name in missing:
            print(f"  {name}")
        return 1

    pairs = [
        (home_id, away_id)
        for home_id, away_id in db.query(Fixture.home_team_id, Fixture.away_team_id)
        .filter(Fixture.tournament_id == tourney.id)
        .all()
        if home_id is not None and away_id is not None
    ]
    problems = check_groups(team_ids_by_canonical, pairs)
    if problems:
        print("Fixture graph does not match the draw. Nothing written.")
        for problem in problems:
            print(f"  {problem}")
        return 1

    print(f"Tournament {tourney.id}: {len(rows)} teams match the draw and the {len(pairs)} fixtures.")
    for code in sorted(GROUPS):
        division, number = code[0], code[1:]
        print(f"  {code}: {', '.join(GROUPS[code])}")

    if not execute:
        print("Dry run. Pass --execute to write division and group_name.")
        return 0

    by_id = {team.id: tt for tt, team in rows}
    for name, team_id in team_ids_by_canonical.items():
        division, number = official[name]
        tt = by_id[team_id]
        tt.division = division
        tt.group_name = number
    db.commit()
    print(f"Stamped division and group_name on {len(team_ids_by_canonical)} teams.")
    return 0


def main() -> None:
    execute = "--execute" in sys.argv
    db = SessionLocal()
    try:
        raise SystemExit(stamp(db, execute))
    finally:
        db.close()


if __name__ == "__main__":
    main()
