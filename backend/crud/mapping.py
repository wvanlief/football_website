from typing import Optional, Union
from sqlalchemy.orm import Session
from backend.database import Team, Competition, ExternalTeamMapping, ExternalCompetitionMapping

def get_team_by_external_id(db: Session, provider_name: str, external_id: Union[str, int]) -> Optional[Team]:
    """Retrieves internal Team entity by external provider ID."""
    ext_id_str = str(external_id)
    mapping = db.query(ExternalTeamMapping).filter(
        ExternalTeamMapping.provider_name == provider_name,
        ExternalTeamMapping.external_id == ext_id_str
    ).first()
    if mapping:
        return mapping.team
    return None

def link_team_external_id(db: Session, team_id: int, provider_name: str, external_id: Union[str, int]) -> ExternalTeamMapping:
    """Links or updates an external provider ID for an internal team."""
    ext_id_str = str(external_id)
    mapping = db.query(ExternalTeamMapping).filter(
        ExternalTeamMapping.provider_name == provider_name,
        ExternalTeamMapping.external_id == ext_id_str
    ).first()
    if not mapping:
        mapping = ExternalTeamMapping(
            team_id=team_id,
            provider_name=provider_name,
            external_id=ext_id_str
        )
        db.add(mapping)
        db.flush()
    elif mapping.team_id != team_id:
        mapping.team_id = team_id
        db.flush()
    return mapping

def get_competition_by_external_id(db: Session, provider_name: str, external_id: Union[str, int]) -> Optional[Competition]:
    """Retrieves internal Competition entity by external provider ID."""
    ext_id_str = str(external_id)
    mapping = db.query(ExternalCompetitionMapping).filter(
        ExternalCompetitionMapping.provider_name == provider_name,
        ExternalCompetitionMapping.external_id == ext_id_str
    ).first()
    if mapping:
        return mapping.competition
    return None

def get_external_id_for_competition(
    db: Session, competition_id: int, provider_name: str
) -> Optional[str]:
    """Return the stored external id for a competition on a given provider."""
    mapping = db.query(ExternalCompetitionMapping).filter(
        ExternalCompetitionMapping.competition_id == competition_id,
        ExternalCompetitionMapping.provider_name == provider_name,
    ).first()
    return mapping.external_id if mapping else None

def link_competition_external_id(db: Session, competition_id: int, provider_name: str, external_id: Union[str, int]) -> ExternalCompetitionMapping:
    """Links or updates an external provider ID for an internal competition."""
    ext_id_str = str(external_id)
    mapping = db.query(ExternalCompetitionMapping).filter(
        ExternalCompetitionMapping.provider_name == provider_name,
        ExternalCompetitionMapping.external_id == ext_id_str
    ).first()
    if not mapping:
        mapping = ExternalCompetitionMapping(
            competition_id=competition_id,
            provider_name=provider_name,
            external_id=ext_id_str
        )
        db.add(mapping)
        db.flush()
    elif mapping.competition_id != competition_id:
        mapping.competition_id = competition_id
        db.flush()
    return mapping
