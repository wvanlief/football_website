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
    is_predicted: Optional[bool] = False

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
    date: Optional[str] = None
    matchup_status: Optional[str] = "predicted"
    match_num: Optional[int] = None

class BracketResponse(BaseModel):
    r32: List[BracketMatch]
    r16: List[BracketMatch]
    qf: List[BracketMatch]
    sf: List[BracketMatch]
    third: BracketMatch
    final: BracketMatch
    champion: str

class TeamProbability(BaseModel):
    team: str
    elo: int
    group_name: Optional[str] = None
    group_exit_pct: float
    r32_exit_pct: float
    r16_exit_pct: float
    qf_exit_pct: float
    sf_exit_pct: float
    runner_up_pct: float
    champion_pct: float

class CombinedBracketResponse(BaseModel):
    bracket: BracketResponse
    probabilities: List[TeamProbability]
    last_updated: Optional[str] = None
    num_simulations: Optional[int] = None

class CountrySimpleOut(BaseModel):
    name: str
    elo: int
    group_name: Optional[str] = None


class ThirdPlacedTeamStanding(TeamStanding):
    group: str

