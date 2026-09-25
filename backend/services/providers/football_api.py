"""API-Football v3 fixture overlay. Not Football-Data.org.

One fixtures call per league. Squad endpoints and badge CDN hosts are out of scope.
"""
from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from backend.utils import fetch_json_with_retry
from backend.services.ingestion.team_resolver import TeamResolver

PROVIDER_NAME = "football_api"
BASE_URL = "https://v3.football.api-sports.io"

# Catalog ids that are not on the Football-Data.org free plan.
LEAGUE_ID_BY_NAME = {
    "UEFA Europa League": 3,
    "UEFA Conference League": 848,
}

STATUS_MAP = {
    "NS": "Scheduled",
    "TBD": "Scheduled",
    "PST": "Postponed",
    "CANC": "Postponed",
    "ABD": "Postponed",
    "AWD": "Postponed",
    "WO": "Postponed",
    "1H": "Live",
    "HT": "Live",
    "2H": "Live",
    "ET": "Live",
    "BT": "Live",
    "P": "Live",
    "LIVE": "Live",
    "INT": "Live",
    "FT": "Finished",
    "AET": "Finished",
    "PEN": "Finished",
}


def get_football_api_key() -> Optional[str]:
    value = os.getenv("FOOTBALLAPI_API_KEY")
    return value or None


def _parse_date(raw: Optional[str]) -> Optional[datetime]:
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _stage_and_matchday(round_name: Optional[str]) -> tuple[str, Optional[int]]:
    text = (round_name or "").strip()
    lower = text.lower()
    matchday = None
    numbered = re.search(r"(\d+)\s*$", text)
    if numbered:
        matchday = int(numbered.group(1))
    if "league stage" in lower or "league phase" in lower:
        return "League Phase", matchday
    if "qualif" in lower:
        return "Qualifying", None
    if "group" in lower:
        return "Group Stage", matchday
    return "Regular Season", matchday


class FootballApiProvider:
    """Fetch a season fixture list from API-Football and normalize it for upsert."""

    def __init__(self, api_key: Optional[str] = None, team_resolver: Optional[TeamResolver] = None):
        self.api_key = api_key if api_key is not None else get_football_api_key()
        self.team_resolver = team_resolver or TeamResolver()
        self.last_request_skipped = False

    def fetch_fixtures(
        self,
        competition_name: str,
        season: int,
        league_id: Optional[int] = None,
    ) -> list[dict]:
        resolved_league = league_id or LEAGUE_ID_BY_NAME.get(competition_name)
        if not resolved_league or not self.api_key:
            return []
        self.last_request_skipped = False
        url = f"{BASE_URL}/fixtures?league={resolved_league}&season={season}"
        try:
            payload = fetch_json_with_retry(
                url,
                headers={"x-apisports-key": self.api_key},
                use_cache=False,
                provider="football_api",
            )
        except Exception as exc:
            print(f"Football-API error for {competition_name}: {exc}")
            return []
        if not isinstance(payload, dict):
            return []
        response = payload.get("response") or []
        return response if isinstance(response, list) else []

    def fetch_fixtures_by_date(self, match_date: str) -> tuple[list[dict], bool]:
        """One ``GET /fixtures?date=`` call.

        Returns ``(fixtures, failed)``. ``failed`` is true on HTTP 4xx or transport
        errors. An empty 200 is ``([], False)``.
        """
        if not self.api_key:
            return [], False
        url = f"{BASE_URL}/fixtures?date={match_date}"
        try:
            payload = fetch_json_with_retry(
                url,
                headers={"x-apisports-key": self.api_key},
                use_cache=False,
                provider="football_api",
            )
        except Exception as exc:
            print(f"Football-API date error for {match_date}: {exc}")
            return [], True
        if not isinstance(payload, dict):
            return [], True
        response = payload.get("response") or []
        if not isinstance(response, list):
            return [], True
        return response, False

    def normalize_fixture_payload(
        self,
        db: Session,
        item: dict,
        tournament_id: int,
        competition_type: str = "Cup",
    ) -> Optional[dict]:
        fixture = item.get("fixture") or {}
        fixture_id = fixture.get("id")
        date_utc = _parse_date(fixture.get("date"))
        teams = item.get("teams") or {}
        home = teams.get("home") or {}
        away = teams.get("away") or {}
        home_name = home.get("name") or ""
        away_name = away.get("name") or ""
        if fixture_id is None or not date_utc or not home_name or not away_name:
            return None

        team_type = "National" if competition_type == "International" else "Club"
        home_team = self.team_resolver.resolve(
            db,
            provider_name=PROVIDER_NAME,
            raw_name=home_name,
            external_id=home.get("id"),
            team_type=team_type,
        )
        away_team = self.team_resolver.resolve(
            db,
            provider_name=PROVIDER_NAME,
            raw_name=away_name,
            external_id=away.get("id"),
            team_type=team_type,
        )

        league = item.get("league") or {}
        stage, matchday = _stage_and_matchday(league.get("round"))
        short = ((fixture.get("status") or {}).get("short") or "NS").upper()
        status = STATUS_MAP.get(short, "Scheduled")
        goals = item.get("goals") or {}
        home_score = goals.get("home")
        away_score = goals.get("away")

        return {
            "api_id": f"fa_{fixture_id}",
            "provider": PROVIDER_NAME,
            "provider_name": PROVIDER_NAME,
            "tournament_id": tournament_id,
            "home_team": home_team,
            "away_team": away_team,
            "home_team_name": home_name,
            "away_team_name": away_name,
            "date_utc": date_utc,
            "stage": stage,
            "matchday_number": matchday,
            "status": status,
            "home_score": home_score,
            "away_score": away_score,
        }
