import os
from typing import Dict, List, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from backend.utils import fetch_json_with_retry
from backend.services.ingestion import NameNormalizer
from backend.crud.mapping import (
    get_team_by_external_id,
    link_team_external_id,
    get_competition_by_external_id,
    link_competition_external_id
)
from backend.database import Team, Competition

PROVIDER_NAME = "football_data"

COMPETITION_CODE_MAP: Dict[str, str] = {
    "Premier League": "PL",
    "La Liga": "PD",
    "Serie A": "SA",
    "Bundesliga": "BL1",
    "Ligue 1": "FL1",
    "Eredivisie": "DED",
    "Primeira Liga": "PPL",
    "UEFA Champions League": "CL",
    "FIFA World Cup": "WC",
    "European Championship": "EC",
    "EFL Championship": "ELC",
}

STATUS_MAP = {
    "FINISHED": "Finished",
    "IN_PLAY": "Live",
    "PAUSED": "Live",
    "HALF_TIME": "Live",
    "SCHEDULED": "Scheduled",
    "TIMED": "Scheduled",
    "POSTPONED": "Scheduled",
    "CANCELLED": "Scheduled",
}

STAGE_MAP = {
    "REGULAR_SEASON": "Regular Season",
    "GROUP_STAGE": "Group Stage",
    "ROUND_OF_16": "Round of 16",
    "QUARTER_FINALS": "Quarter-final",
    "SEMI_FINALS": "Semi-final",
    "FINAL": "Final",
}

class FootballDataProvider:
    """
    Provider client for Football-Data.org (v4 API).
    Fetches teams and matches, normalizes domain entities,
    and maintains external entity mappings in the database.
    """
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("FOOTBALL_DATA_ORG_KEY") or os.getenv("FOOTBALL_DATA_KEY")
        self.normalizer = NameNormalizer()

    def get_headers(self) -> Dict[str, str]:
        headers = {"User-Agent": "Mozilla/5.0"}
        if self.api_key:
            headers["X-Auth-Token"] = self.api_key
        return headers

    def call_api(self, endpoint: str, params: Optional[dict] = None) -> dict:
        query = ""
        if params:
            query = "?" + "&".join(f"{k}={v}" for k, v in params.items())
        url = f"https://api.football-data.org/v4/{endpoint}{query}"
        return fetch_json_with_retry(url, headers=self.get_headers(), provider="football_data_org")

    def get_competition_code(self, competition_name: str) -> Optional[str]:
        return COMPETITION_CODE_MAP.get(competition_name)

    def fetch_fixtures(self, competition_name: str, season: int) -> List[dict]:
        code = self.get_competition_code(competition_name)
        if not code:
            print(f"Football-Data.org: Competition '{competition_name}' not mapped to a code.")
            return []
        
        try:
            res = self.call_api(f"competitions/{code}/matches", {"season": season})
            if not isinstance(res, dict) or "matches" not in res:
                return []
            return res.get("matches", [])
        except Exception as e:
            print(f"Football-Data.org API error fetching fixtures for {competition_name}: {e}")
            return []

    def fetch_teams(self, competition_name: str, season: int) -> List[dict]:
        code = self.get_competition_code(competition_name)
        if not code:
            return []
        try:
            res = self.call_api(f"competitions/{code}/teams", {"season": season})
            if not isinstance(res, dict) or "teams" not in res:
                return []
            return res.get("teams", [])
        except Exception as e:
            print(f"Football-Data.org API error fetching teams for {competition_name}: {e}")
            return []

    def resolve_team(self, db: Session, raw_team_info: dict, team_type: str = "Club") -> Optional[Team]:
        """
        Resolves a raw Football-Data team dict to an internal Team DB entity:
        1. Queries external_team_mappings by (provider_name='football_data', external_id)
        2. Queries team by normalized name
        3. If missing, creates a new Team row and registers mapping.
        """
        ext_id = str(raw_team_info.get("id")) if raw_team_info.get("id") is not None else None
        if ext_id:
            team = get_team_by_external_id(db, PROVIDER_NAME, ext_id)
            if team:
                return team

        raw_name = raw_team_info.get("shortName") or raw_team_info.get("name", "")
        norm_name = self.normalizer.normalize(raw_name)
        
        team = db.query(Team).filter(Team.name == norm_name).first()
        if not team and raw_team_info.get("name"):
            full_norm = self.normalizer.normalize(raw_team_info["name"])
            team = db.query(Team).filter(Team.name == full_norm).first()
            
        if not team and norm_name:
            country = raw_team_info.get("area", {}).get("name")
            country_code = self.normalizer.get_country_code(country) if country else None
            team = Team(
                name=norm_name,
                country_code=country_code,
                team_type=team_type,
                elo=1500,
                form_score=50.0
            )
            db.add(team)
            db.flush()

        if ext_id and team:
            link_team_external_id(db, team.id, PROVIDER_NAME, ext_id)

        return team

    def normalize_fixture_payload(self, db: Session, item: dict, tournament_id: int, competition_type: str = "League") -> Optional[dict]:
        """
        Normalizes a raw Football-Data.org match item into findingfootball.games domain structure.
        """
        match_id = str(item.get("id"))
        date_utc_str = item.get("utcDate")
        if not date_utc_str:
            return None

        try:
            date_utc = datetime.fromisoformat(date_utc_str.replace('Z', '+00:00'))
        except Exception:
            return None

        home_raw = item.get("homeTeam", {})
        away_raw = item.get("awayTeam", {})

        team_type = "National" if competition_type == "International" else "Club"
        home_team = self.resolve_team(db, home_raw, team_type=team_type)
        away_team = self.resolve_team(db, away_raw, team_type=team_type)

        status_raw = item.get("status", "SCHEDULED")
        status = STATUS_MAP.get(status_raw, "Scheduled")

        raw_stage = item.get("stage", "REGULAR_SEASON")
        stage = STAGE_MAP.get(raw_stage, raw_stage)

        matchday = item.get("matchday")

        full_time_score = item.get("score", {}).get("fullTime", {})
        home_score = full_time_score.get("home") if full_time_score else None
        away_score = full_time_score.get("away") if full_time_score else None

        return {
            "api_id": f"fd_{match_id}",
            "raw_id": match_id,
            "provider": PROVIDER_NAME,
            "tournament_id": tournament_id,
            "home_team": home_team,
            "away_team": away_team,
            "home_team_id": home_team.id if home_team else None,
            "away_team_id": away_team.id if away_team else None,
            "date_utc": date_utc,
            "stage": stage,
            "matchday_number": matchday,
            "status": status,
            "home_score": home_score,
            "away_score": away_score,
        }
