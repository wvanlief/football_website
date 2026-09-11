from typing import Optional
from sqlalchemy.orm import Session
from backend.database import Team
from backend.crud.mapping import get_team_by_external_id, link_team_external_id
from backend.services.ingestion.normalizer import NameNormalizer


def is_placeholder(name: str) -> bool:
    if not name:
        return True
    n_lower = name.lower().strip()
    if n_lower in ("0", "tbd", "placeholder", "unknown", "null", "none"):
        return True
    if n_lower.startswith("winner") or n_lower.startswith("runner") or n_lower.startswith("loser"):
        return True
    return False


class TeamResolver:
    """
    Unified team resolution service following ADR-0002.
    Resolves external team identifiers to database Team entities safely without data duplication.
    """
    def __init__(self, normalizer: Optional[NameNormalizer] = None):
        self.normalizer = normalizer or NameNormalizer()

    def resolve(
        self,
        db: Session,
        provider_name: str,
        raw_name: str,
        external_id: Optional[str | int] = None,
        team_type: str = "Club",
        default_elo: int = 1500,
        country_code: Optional[str] = None,
        api_id: Optional[int] = None,
        logo_url: Optional[str] = None,
        elo_source: Optional[str] = None,
        alt_names: Optional[list[str]] = None,
    ) -> Optional[Team]:
        """
        Resolves a raw API team payload to an internal database Team entity.
        Returns None for placeholder team strings.
        """
        if not raw_name or is_placeholder(raw_name):
            return None

        # 1. Check ExternalTeamMapping
        if provider_name and external_id is not None and str(external_id) != "0":
            mapped_team = get_team_by_external_id(db, provider_name=provider_name, external_id=external_id)
            if mapped_team:
                if logo_url and not mapped_team.logo_url:
                    mapped_team.logo_url = logo_url
                    db.flush()
                return mapped_team

        candidate_names: list[str] = []
        for name in [raw_name, *(alt_names or [])]:
            if not name:
                continue
            stripped = name.strip()
            if stripped and stripped not in candidate_names:
                candidate_names.append(stripped)

        team = self._find_existing(db, candidate_names, team_type, api_id)
        if team:
            if provider_name and external_id is not None:
                link_team_external_id(db, team_id=team.id, provider_name=provider_name, external_id=external_id)
            if api_id and team.api_id is None:
                team.api_id = api_id
            if logo_url and not team.logo_url:
                team.logo_url = logo_url
            db.flush()
            return team

        # Create new Team if not found. Prefer the first (usually official) name.
        canonical = self.normalizer.normalize(candidate_names[0]) if candidate_names else raw_name.strip()
        calc_country_code = country_code
        if not calc_country_code and team_type == "National" and canonical:
            calc_country_code = self.normalizer.get_country_code(canonical)
        if not calc_country_code and canonical:
            calc_country_code = canonical[:3].upper()

        form_score = round(min(95.0, max(45.0, 50.0 + (default_elo - 1500) * 0.05)), 1)
        resolved_elo_source = elo_source or (
            "clubelo" if team_type == "Club" else "eloratings"
        )

        new_team = Team(
            name=canonical or raw_name.strip(),
            country_code=calc_country_code,
            team_type=team_type,
            elo_source=resolved_elo_source,
            elo=default_elo,
            form_score=form_score,
            api_id=api_id,
            logo_url=logo_url
        )
        db.add(new_team)
        db.flush()

        if provider_name and external_id is not None:
            link_team_external_id(db, team_id=new_team.id, provider_name=provider_name, external_id=external_id)

        return new_team

    def _find_existing(
        self,
        db: Session,
        candidate_names: list[str],
        team_type: str,
        api_id: Optional[int],
    ) -> Optional[Team]:
        seen_keys: list[str] = []
        for name in candidate_names:
            norm_name = self.normalizer.normalize(name)
            if norm_name:
                team = db.query(Team).filter(Team.name == norm_name).first()
                if team:
                    return team
            if name != norm_name:
                team = db.query(Team).filter(Team.name == name).first()
                if team:
                    return team
            key = self.normalizer.lookup_key(name)
            if key and key not in seen_keys:
                seen_keys.append(key)

        if api_id:
            team = db.query(Team).filter(Team.api_id == api_id).first()
            if team:
                return team

        if not seen_keys:
            return None

        clubs = (
            db.query(Team)
            .filter(Team.team_type == team_type)
            .all()
        )
        matches: list[Team] = []
        for club in clubs:
            club_key = self.normalizer.lookup_key(club.name)
            if club_key in seen_keys:
                matches.append(club)

        if not matches:
            return None
        if len(matches) == 1:
            return matches[0]
        rated = [m for m in matches if m.elo and m.elo != 1500]
        pool = rated or matches
        with_api = [m for m in pool if m.api_id]
        pool = with_api or pool
        return sorted(pool, key=lambda m: m.id)[0]
