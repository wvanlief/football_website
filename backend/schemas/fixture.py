from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from backend.schemas.team import TeamOut

class OddsSchema(BaseModel):
    home: float
    draw: float
    away: float

class WatchabilitySchema(BaseModel):
    overall: float
    competitiveness: float
    odds: float
    form: float
    narrative: float

class FixtureOut(BaseModel):
    id: int
    home_team: TeamOut
    away_team: TeamOut
    date: str
    formatted_time: str
    formatted_date: str
    formatted_date_short: str
    stage: str
    group_name: Optional[str] = None
    status: str
    score: Optional[str] = None
    odds: OddsSchema
    watchability: WatchabilitySchema
    reasons: List[str] = []

    model_config = ConfigDict(from_attributes=True)

class GroupedFixturesResponse(BaseModel):
    today: List[FixtureOut]
    tomorrow: List[FixtureOut]
    this_week: List[FixtureOut]
    finished: List[FixtureOut]

class CalendarTeamOut(BaseModel):
    name: str

    model_config = ConfigDict(from_attributes=True)

class CalendarFixtureOut(BaseModel):
    id: int
    home_team: CalendarTeamOut
    away_team: CalendarTeamOut
    date: str
    formatted_time: str
    formatted_date: str
    formatted_date_short: str
    stage: str
    status: str
    score: Optional[str] = None
    watchability_score: float

    model_config = ConfigDict(from_attributes=True)
