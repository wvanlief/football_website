"""Merge draw-seeded duplicate clubs onto canonical catalog teams."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from backend.database import (
    EloHistory,
    ExternalTeamMapping,
    Fixture,
    PlayerContract,
    Team,
    TournamentTeam,
)
from backend.services.ingestion.normalizer import TEAM_NAME_ALIASES, NameNormalizer
from backend.services.elo import elo_to_form, fetch_clubelo_ratings, fuzzy_match_team, record_elo_history


DRAW_ELO_FALLBACK = {
    "Club Brugge KV": 1710,
    "BSC Young Boys": 1640,
    "Red Bull Salzburg": 1700,
}

_REVIEW_FILE = Path("backend/data/elo_name_review.json")


def _approved_review_elos() -> dict[str, tuple[str, int]]:
    if not _REVIEW_FILE.exists():
        return {}
    try:
        payload = json.loads(_REVIEW_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    out = {}
    for item in payload:
        if item.get("status") != "approved":
            continue
        name = item.get("api_football_name")
        elo = item.get("elo")
        if name and elo:
            out[name] = (item.get("clubelo_name") or name, int(elo))
    return out


CLUB_ALIASES = {
    alias: canonical
    for alias, canonical in TEAM_NAME_ALIASES.items()
    if alias not in (
        "Korea Republic",
        "Czech Republic",
        "Bosnia & Herzegovina",
        "Bosnia & Herzegov.",
        "Bosnia & Herz.",
        "Cote d'Ivoire",
        "Ivory Coast",
        "Curacao",
        "United States",
    )
}


def _find_team(db: Session, name: str) -> Team | None:
    team = db.query(Team).filter(Team.name == name).first()
    if team:
        return team
    return db.query(Team).filter(Team.name == NameNormalizer().normalize(name)).first()


def merge_team_into(db: Session, source: Team, target: Team) -> None:
    """Rewire all FKs from source onto target, then delete source."""
    if source.id == target.id:
        return

    for fixture in db.query(Fixture).filter(Fixture.home_team_id == source.id).all():
        fixture.home_team_id = target.id
    for fixture in db.query(Fixture).filter(Fixture.away_team_id == source.id).all():
        fixture.away_team_id = target.id
    for fixture in db.query(Fixture).filter(Fixture.winner_id == source.id).all():
        fixture.winner_id = target.id

    for tt in db.query(TournamentTeam).filter(TournamentTeam.team_id == source.id).all():
        already = (
            db.query(TournamentTeam)
            .filter(
                TournamentTeam.tournament_id == tt.tournament_id,
                TournamentTeam.team_id == target.id,
            )
            .first()
        )
        if already:
            db.delete(tt)
        else:
            tt.team_id = target.id

    for contract in db.query(PlayerContract).filter(PlayerContract.team_id == source.id).all():
        contract.team_id = target.id

    for history in db.query(EloHistory).filter(EloHistory.team_id == source.id).all():
        history.team_id = target.id

    for mapping in db.query(ExternalTeamMapping).filter(ExternalTeamMapping.team_id == source.id).all():
        clash = (
            db.query(ExternalTeamMapping)
            .filter(
                ExternalTeamMapping.provider_name == mapping.provider_name,
                ExternalTeamMapping.external_id == mapping.external_id,
                ExternalTeamMapping.id != mapping.id,
            )
            .first()
        )
        if clash:
            db.delete(mapping)
        else:
            mapping.team_id = target.id

    if (not target.elo or target.elo == 1500) and source.elo and source.elo != 1500:
        target.elo = source.elo
        target.form_score = source.form_score or elo_to_form(source.elo)

    db.flush()
    db.delete(source)
    db.flush()


def merge_club_aliases(db: Session, commit: bool = True) -> list[str]:
    """Merge known draw-name duplicates onto canonical club rows. Returns log lines."""
    logs = []
    for alias, canonical in CLUB_ALIASES.items():
        source = _find_team(db, alias)
        target = _find_team(db, canonical)
        if source and target and source.id != target.id:
            logs.append(f"Merged '{source.name}' (id={source.id}) -> '{target.name}' (id={target.id}, api_id={target.api_id})")
            merge_team_into(db, source, target)
        elif source and not target:
            logs.append(f"Skipped '{alias}': canonical '{canonical}' not in DB")
        elif not source:
            logs.append(f"No duplicate named '{alias}'")
    if commit:
        db.commit()
    else:
        db.flush()
    return logs


def apply_clubelo_to_canonical_clubs(
    db: Session,
    canonical_names: list[str] | None = None,
    fetch_live: bool = True,
) -> list[str]:
    """Pull ClubElo for merged canonical clubs and write ratings + history."""
    names = canonical_names or sorted(set(CLUB_ALIASES.values()))
    ratings = fetch_clubelo_ratings() if fetch_live else {}
    review_elos = _approved_review_elos()
    logs = []
    now = datetime.now(timezone.utc)
    clubelo_names = list(ratings.keys()) if ratings else []

    for name in names:
        team = _find_team(db, name)
        if not team:
            logs.append(f"ClubElo skip: '{name}' not in DB")
            continue

        elo = None
        source = None
        if ratings:
            best, confidence = fuzzy_match_team(team.name, clubelo_names)
            if confidence < 0.85:
                for alias, canonical in CLUB_ALIASES.items():
                    if canonical == team.name and alias in ratings:
                        best, confidence = alias, 1.0
                        break
            if confidence >= 0.85 and best in ratings:
                elo = ratings[best]
                source = f"ClubElo '{best}' conf={confidence:.2f}"

        if elo is None and team.name in review_elos:
            clubelo_name, elo = review_elos[team.name]
            source = f"review file '{clubelo_name}'"

        if elo is None and team.name in DRAW_ELO_FALLBACK:
            elo = DRAW_ELO_FALLBACK[team.name]
            source = "UEFA draw fallback"

        if elo is None:
            logs.append(f"ClubElo skip '{team.name}': no rating source")
            continue

        team.elo = elo
        team.form_score = elo_to_form(elo)
        record_elo_history(db, team.id, elo, now)
        logs.append(f"ELO {elo} -> {team.name} ({source})")
    db.commit()
    return logs
