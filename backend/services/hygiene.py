"""Report-only database hygiene.

Detects split seasons, duplicate fixtures, World Cup dates on the wrong
tournament, and leftover unstamped European-cup rows. Never mutates the
database and has no execute flag. A human reads the report.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from backend.database import Competition, Fixture, FixtureOdds, Tournament

REPORT_PATH = Path(__file__).resolve().parents[1] / "data" / "hygiene_report.json"

EUROPEAN_CUPS = (
    "UEFA Champions League",
    "UEFA Europa League",
    "UEFA Conference League",
)

_LEFTOVER_NOTE = (
    "Counts only. Human review of scheduled unstamped European-cup rows is "
    "issue #145. Overlay stays additive."
)


def _calendar_day(value: datetime | None) -> str:
    if value is None:
        return ""
    return value.strftime("%Y-%m-%d")


def _season_start_year(season_name: str | None) -> str | None:
    if not season_name:
        return None
    match = re.match(r"(\d{4})", season_name.strip())
    return match.group(1) if match else None


def _stamped(api_id) -> bool:
    return api_id is not None and str(api_id).strip() != ""


def _split_seasons(db: Session) -> list[dict]:
    competitions = db.query(Competition).all()
    findings = []
    for competition in competitions:
        tournaments = (
            db.query(Tournament)
            .filter(Tournament.competition_id == competition.id)
            .all()
        )
        by_year: dict[str, list[Tournament]] = {}
        for tournament in tournaments:
            year = _season_start_year(tournament.season_name)
            if year is None:
                continue
            by_year.setdefault(year, []).append(tournament)
        for year, group in sorted(by_year.items()):
            names = {tournament.season_name for tournament in group}
            if len(group) < 2 or len(names) < 2:
                continue
            fixtures_by_tournament = {
                tournament.id: db.query(Fixture).filter(Fixture.tournament_id == tournament.id).all()
                for tournament in group
            }
            index: dict[tuple, list[int]] = {}
            for tournament in group:
                for fixture in fixtures_by_tournament[tournament.id]:
                    key = (fixture.home_team_id, fixture.away_team_id, _calendar_day(fixture.date_utc))
                    index.setdefault(key, []).append(fixture.id)
            shared = [
                {
                    "home_team_id": home_id,
                    "away_team_id": away_id,
                    "date": day,
                    "fixture_ids": sorted(ids),
                }
                for (home_id, away_id, day), ids in sorted(index.items(), key=lambda item: (item[0][2], item[0][0] or 0, item[0][1] or 0))
                if len(ids) > 1
            ]
            if not shared:
                continue
            findings.append({
                "competition_id": competition.id,
                "competition": competition.name,
                "season_start_year": year,
                "tournaments": [
                    {"id": tournament.id, "season_name": tournament.season_name, "status": tournament.status}
                    for tournament in sorted(group, key=lambda row: row.id)
                ],
                "shared_pairings": shared,
            })
    return findings


def _duplicate_fixtures(db: Session) -> list[dict]:
    odds_ids = {row[0] for row in db.query(FixtureOdds.fixture_id).all()}
    active_tournaments = db.query(Tournament).filter(Tournament.status != "Completed").all()
    competition_names = {
        competition.id: competition.name
        for competition in db.query(Competition).all()
    }
    findings = []
    for tournament in active_tournaments:
        fixtures = db.query(Fixture).filter(Fixture.tournament_id == tournament.id).all()
        grouped: dict[tuple, list[Fixture]] = {}
        for fixture in fixtures:
            key = (fixture.home_team_id, fixture.away_team_id, _calendar_day(fixture.date_utc))
            grouped.setdefault(key, []).append(fixture)
        for (home_id, away_id, day), rows in sorted(grouped.items(), key=lambda item: (item[0][2], item[0][0] or 0)):
            if len(rows) < 2:
                continue
            def rank(fixture: Fixture) -> tuple:
                finished = 1 if fixture.status == "Finished" else 0
                has_odds = 1 if fixture.id in odds_ids else 0
                return (finished, has_odds, -fixture.id)

            authoritative = max(rows, key=rank)
            reasons = []
            if authoritative.status == "Finished":
                reasons.append("Finished")
            if authoritative.id in odds_ids:
                reasons.append("has odds")
            if authoritative.id == min(row.id for row in rows):
                reasons.append("lowest id")
            if not reasons:
                reasons.append("lowest id")
            findings.append({
                "tournament_id": tournament.id,
                "competition": competition_names.get(tournament.competition_id),
                "home_team_id": home_id,
                "away_team_id": away_id,
                "date": day,
                "authoritative_fixture_id": authoritative.id,
                "authoritative_because": ", ".join(reasons),
                "rows": [
                    {
                        "id": fixture.id,
                        "status": fixture.status,
                        "has_odds": fixture.id in odds_ids,
                    }
                    for fixture in sorted(rows, key=lambda row: row.id)
                ],
            })
    return findings


def _world_cup_window(db: Session) -> tuple[Competition | None, datetime | None, datetime | None]:
    competitions = db.query(Competition).all()
    world_cups = [
        competition for competition in competitions
        if competition.name == "FIFA World Cup"
        or (
            "world cup" in (competition.name or "").lower()
            and "club" not in (competition.name or "").lower()
        )
    ]
    if not world_cups:
        return None, None, None
    world_cups.sort(key=lambda competition: (competition.name != "FIFA World Cup", competition.id))
    competition = world_cups[0]
    tournament_ids = [
        row[0]
        for row in db.query(Tournament.id).filter(Tournament.competition_id == competition.id).all()
    ]
    if not tournament_ids:
        return competition, None, None
    dates = [
        row[0]
        for row in db.query(Fixture.date_utc).filter(Fixture.tournament_id.in_(tournament_ids)).all()
        if row[0] is not None
    ]
    if not dates:
        return competition, None, None
    return competition, min(dates), max(dates)


def _world_cup_dates_on_other_tournaments(db: Session) -> dict:
    competition, start, end = _world_cup_window(db)
    payload = {
        "world_cup_competition": competition.name if competition else None,
        "window_start": _calendar_day(start) or None,
        "window_end": _calendar_day(end) or None,
        "rows": [],
    }
    if competition is None or start is None or end is None:
        return payload
    start_day = _calendar_day(start)
    end_day = _calendar_day(end)
    rows = (
        db.query(Fixture, Competition.name)
        .join(Tournament, Fixture.tournament_id == Tournament.id)
        .join(Competition, Tournament.competition_id == Competition.id)
        .filter(Competition.id != competition.id)
        .all()
    )
    flagged = []
    for fixture, competition_name in rows:
        day = _calendar_day(fixture.date_utc)
        if start_day <= day <= end_day:
            flagged.append({
                "fixture_id": fixture.id,
                "tournament_id": fixture.tournament_id,
                "competition": competition_name,
                "date": day,
                "home_team_id": fixture.home_team_id,
                "away_team_id": fixture.away_team_id,
            })
    flagged.sort(key=lambda row: (row["date"], row["fixture_id"]))
    payload["rows"] = flagged
    return payload


def _european_cup_leftovers(db: Session) -> dict:
    counts = {name: 0 for name in EUROPEAN_CUPS}
    competitions = db.query(Competition).filter(Competition.name.in_(EUROPEAN_CUPS)).all()
    for competition in competitions:
        tournament_ids = [
            row[0]
            for row in db.query(Tournament.id).filter(
                Tournament.competition_id == competition.id,
                Tournament.status != "Completed",
            ).all()
        ]
        if not tournament_ids:
            continue
        fixtures = db.query(Fixture).filter(Fixture.tournament_id.in_(tournament_ids)).all()
        stamped_pairs = {
            (fixture.tournament_id, fixture.home_team_id, fixture.away_team_id)
            for fixture in fixtures
            if _stamped(fixture.api_id)
        }
        leftovers = 0
        for fixture in fixtures:
            if fixture.status != "Scheduled" or _stamped(fixture.api_id):
                continue
            pair = (fixture.tournament_id, fixture.home_team_id, fixture.away_team_id)
            if pair in stamped_pairs:
                continue
            leftovers += 1
        counts[competition.name] = leftovers
    return {
        "issue": 145,
        "note": _LEFTOVER_NOTE,
        "counts": counts,
        "total": sum(counts.values()),
    }


def build_hygiene_report(db: Session) -> dict:
    """Inspect the database and return a structured report. Does not write."""
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "split_seasons": _split_seasons(db),
        "duplicate_fixtures": _duplicate_fixtures(db),
        "world_cup_dates_on_other_tournaments": _world_cup_dates_on_other_tournaments(db),
        "european_cup_leftovers": _european_cup_leftovers(db),
    }


def run_hygiene_report(db: Session, report_path: Path | None = None) -> dict:
    """Build the report and store it as JSON. The database is not modified."""
    report = build_hygiene_report(db)
    path = Path(report_path) if report_path is not None else REPORT_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def load_last_hygiene_report(report_path: Path | None = None) -> dict | None:
    path = Path(report_path) if report_path is not None else REPORT_PATH
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    from backend.database import SessionLocal

    db = SessionLocal()
    try:
        report = run_hygiene_report(db)
    finally:
        db.close()
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
