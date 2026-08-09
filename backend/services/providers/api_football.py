import os
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone

from backend.utils import fetch_json_with_retry
from backend.services.ingestion.normalizer import NameNormalizer

PROVIDER_NAME = "api_football"

STATUS_MAP = {
    "FT": "Finished",
    "AET": "Finished",
    "PEN": "Finished",
    "1H": "Live",
    "2H": "Live",
    "HT": "Live",
    "ET": "Live",
    "P": "Live",
    "LIVE": "Live",
    "NS": "Scheduled",
    "TBD": "Scheduled",
    "PST": "Scheduled",
    "CANC": "Scheduled",
    "ABD": "Scheduled",
}


def call_football_api(endpoint: str, params: Optional[dict] = None) -> dict:
    """Standalone helper function to query API-Football (v3 API)."""
    api_key = os.getenv("FOOTBALL_API_KEY") or os.getenv("API_FOOTBALL_KEY")
    if not api_key:
        raise ValueError("FOOTBALL_API_KEY/API_FOOTBALL_KEY is not configured in the environment.")

    query = ""
    if params:
        query = "?" + "&".join(f"{k}={v}" for k, v in params.items())

    url = f"https://v3.football.api-sports.io/{endpoint}{query}"
    headers = {
        "x-apisports-key": api_key,
        "User-Agent": "Mozilla/5.0"
    }
    return fetch_json_with_retry(url, headers=headers)


class ApiFootballProvider:
    """
    Provider client for API-Football (v3 API-Sports).
    Fetches teams and matches, normalizes domain entities,
    and returns standardized domain payloads.
    """
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("FOOTBALL_API_KEY") or os.getenv("API_FOOTBALL_KEY")
        self.normalizer = NameNormalizer()

    def get_headers(self) -> Dict[str, str]:
        headers = {"User-Agent": "Mozilla/5.0"}
        if self.api_key:
            headers["x-apisports-key"] = self.api_key
        return headers

    def call_api(self, endpoint: str, params: Optional[dict] = None) -> dict:
        return call_football_api(endpoint, params)

    def fetch_fixtures(self, league_id: int, season: int) -> List[dict]:
        """Fetches raw fixtures for a league and season from API-Football."""
        try:
            res = self.call_api("fixtures", {"league": league_id, "season": season})
            if not isinstance(res, dict) or "response" not in res:
                return []
            return res.get("response", [])
        except Exception as e:
            print(f"API-Football error fetching fixtures for league {league_id}, season {season}: {e}")
            return []

    def fetch_teams(self, league_id: int, season: int) -> List[dict]:
        """Fetches raw team definitions for a league and season from API-Football."""
        try:
            res = self.call_api("teams", {"league": league_id, "season": season})
            if not isinstance(res, dict) or "response" not in res:
                return []
            return res.get("response", [])
        except Exception as e:
            print(f"API-Football error fetching teams for league {league_id}, season {season}: {e}")
            return []

    def normalize_fixture_payload(self, raw_item: dict) -> dict:
        """
        Normalizes a raw API-Football fixture payload dictionary
        into a standardized domain fixture dictionary.
        """
        fixture_info = raw_item.get("fixture", {})
        teams_info = raw_item.get("teams", {})
        goals_info = raw_item.get("goals", {})
        league_info = raw_item.get("league", {})

        api_id = str(fixture_info.get("id")) if fixture_info.get("id") is not None else None
        status_short = fixture_info.get("status", {}).get("short", "")
        status = STATUS_MAP.get(status_short, "Scheduled")

        date_str = fixture_info.get("date")
        date_utc = datetime.now(timezone.utc)
        if date_str:
            try:
                date_utc = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            except Exception:
                pass

        round_str = league_info.get("round", "")
        matchday_number = None
        stage = "Regular Season"
        if round_str:
            if "Regular Season" in round_str:
                try:
                    matchday_number = int(round_str.split("-")[-1].strip())
                except ValueError:
                    pass
            elif "Group" in round_str:
                stage = "Group Stage"
            else:
                stage = round_str

        home_name = teams_info.get("home", {}).get("name", "")
        away_name = teams_info.get("away", {}).get("name", "")
        home_ext_id = teams_info.get("home", {}).get("id")
        away_ext_id = teams_info.get("away", {}).get("id")

        return {
            "provider_name": PROVIDER_NAME,
            "api_id": api_id,
            "date_utc": date_utc,
            "stage": stage,
            "matchday_number": matchday_number,
            "status": status,
            "home_team_name": self.normalizer.normalize(home_name) if home_name else "",
            "home_team_external_id": str(home_ext_id) if home_ext_id is not None else None,
            "home_team_api_id": home_ext_id,
            "away_team_name": self.normalizer.normalize(away_name) if away_name else "",
            "away_team_external_id": str(away_ext_id) if away_ext_id is not None else None,
            "away_team_api_id": away_ext_id,
            "home_score": goals_info.get("home"),
            "away_score": goals_info.get("away")
        }
