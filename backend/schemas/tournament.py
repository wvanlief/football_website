from typing import List, Optional
from pydantic import BaseModel
from backend.schemas.team import TeamStanding
from backend.schemas.fixture import FixtureOut
from backend.schemas.player import PlayerOut

class CountryDetailsResponse(BaseModel):
    name: str
    elo: int
    group_name: Optional[str] = None
    group_rank: int
    form: List[str]
    players: List[PlayerOut]
    future_matches: List[FixtureOut]

class GroupDetailsResponse(BaseModel):
    group_letter: str
    standings: List[TeamStanding]
    fixtures: List[FixtureOut]

class BracketTeam(BaseModel):
    name: str
    elo: int
    group_name: Optional[str] = None

class BracketMatch(BaseModel):
    team1: BracketTeam
    team2: BracketTeam
    winner: str
    home_score: Optional[int] = None
    away_score: Optional[int] = None
    has_extra_time: Optional[bool] = False
    has_penalties: Optional[bool] = False
    home_penalty_score: Optional[int] = None
    away_penalty_score: Optional[int] = None

class BracketResponse(BaseModel):
    r32: List[BracketMatch]
    r16: List[BracketMatch]
    qf: List[BracketMatch]
    sf: List[BracketMatch]
    third: BracketMatch
    final: BracketMatch
    champion: str
