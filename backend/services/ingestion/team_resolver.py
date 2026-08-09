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
        logo_url: Optional[str] = None
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
                return mapped_team

        norm_name = self.normalizer.normalize(raw_name) if raw_name else ""

        # 2. Match by normalized name
        team = None
        if norm_name:
            team = db.query(Team).filter(Team.name == norm_name).first()

        # 3. Match by raw name if normalized lookup returned nothing
        if not team and raw_name and raw_name != norm_name:
            team = db.query(Team).filter(Team.name == raw_name.strip()).first()

        # 4. Match by api_id if passed
        if not team and api_id:
            team = db.query(Team).filter(Team.api_id == api_id).first()

        # If existing team found through steps 2-4, link external mapping
        if team:
            if provider_name and external_id is not None:
                link_team_external_id(db, team_id=team.id, provider_name=provider_name, external_id=external_id)
            if api_id and team.api_id is None:
                team.api_id = api_id
                db.flush()
            return team

        # 5. Create new Team if not found
        calc_country_code = country_code
        if not calc_country_code and team_type == "National" and norm_name:
            calc_country_code = self.normalizer.get_country_code(norm_name)
        if not calc_country_code and norm_name:
            calc_country_code = norm_name[:3].upper()

        form_score = round(min(95.0, max(45.0, 50.0 + (default_elo - 1500) * 0.05)), 1)
        elo_source = "clubelo" if team_type == "Club" else "eloratings"

        new_team = Team(
            name=norm_name or raw_name.strip(),
            country_code=calc_country_code,
            team_type=team_type,
            elo_source=elo_source,
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
