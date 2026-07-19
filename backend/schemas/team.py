from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from backend.schemas.player import PlayerOut

class TeamSimple(BaseModel):
    name: str
    elo: int
    form_score: float
    win_streak: int

    model_config = ConfigDict(from_attributes=True)

class TeamOut(TeamSimple):
    players: List[PlayerOut] = []

class TeamStanding(BaseModel):
    name: str
    played: int
    won: int
    drawn: int
    lost: int
    goals_for: int
    goals_against: int
    goal_difference: int
    points: int
    elo: int
    qualification_probability: Optional[float] = None
    status: Optional[str] = "Active"
    points_needed_top_2: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)
