"""Highlightly date-page failover. Not a season dump."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlencode

from sqlalchemy.orm import Session

from backend.utils import fetch_json_with_retry
from backend.services.ingestion.team_resolver import TeamResolver

PROVIDER_NAME = "highlightly"
BASE_URL = "https://soccer.highlightly.net"
PAGE_LIMIT = 100
MAX_PAGES = 3

LEAGUE_PHASE_NAMES = {
    "UEFA Europa League",
    "UEFA Conference League",
    "UEFA Europa Conference League",
}


def get_highlightly_api_key() -> Optional[str]:
    value = os.getenv("HIGHLIGHTLY_API_KEY")
    return value or None


def _parse_date(raw: Optional[str]):
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _league_name(item: dict) -> str:
    league = item.get("league")
    if isinstance(league, dict):
        return league.get("name") or ""
    return league or ""


def _team_name(item: dict, flat_key: str, nested_key: str) -> tuple[str, Optional[object]]:
    nested = item.get(nested_key) or {}
    if isinstance(nested, dict) and nested.get("name"):
        return nested.get("name") or "", nested.get("id")
    return item.get(flat_key) or "", None


def _status_and_scores(item: dict) -> tuple[str, Optional[int], Optional[int]]:
    state = item.get("state")
    description = ""
    current = None
    if isinstance(state, dict):
        description = state.get("description") or ""
        current = (state.get("score") or {}).get("current")
    elif isinstance(state, str):
        description = state
        current = item.get("score")
    lowered = description.lower()
    if "finish" in lowered or lowered in {"ft", "ended", "after penalties"}:
        status = "Finished"
    elif any(token in lowered for token in ("live", "half", "progress", "1st", "2nd")):
        status = "Live"
    else:
        status = "Scheduled"
    home_score = away_score = None
    if isinstance(current, str) and "-" in current:
        left, right = current.split("-", 1)
        try:
            home_score, away_score = int(left.strip()), int(right.strip())
        except ValueError:
            home_score = away_score = None
    return status, home_score, away_score


class HighlightlyProvider:
    """Date query against Highlightly, optionally filtered by league name."""

    def __init__(self, api_key: Optional[str] = None, team_resolver: Optional[TeamResolver] = None):
        self.api_key = api_key if api_key is not None else get_highlightly_api_key()
        self.team_resolver = team_resolver or TeamResolver()

    def fetch_matches_by_date(
        self,
        match_date: str,
        league_name: Optional[str] = None,
    ) -> list[dict]:
        if not self.api_key:
            return []
        matches: list[dict] = []
        offset = 0
        for _page in range(MAX_PAGES):
            params = {"date": match_date, "limit": PAGE_LIMIT, "offset": offset}
            if league_name:
                params["leagueName"] = league_name
            url = f"{BASE_URL}/matches?{urlencode(params)}"
            try:
                payload = fetch_json_with_retry(
                    url,
                    headers={"x-rapidapi-key": self.api_key},
                    use_cache=False,
                    provider="highlightly",
                )
            except Exception as exc:
                print(f"Highlightly date error for {match_date}: {exc}")
                break
            if not isinstance(payload, dict):
                break
            page = payload.get("data") or []
            if not isinstance(page, list) or not page:
                break
            matches.extend(page)
            total = (payload.get("pagination") or {}).get("totalCount")
            offset += PAGE_LIMIT
            if total is not None and offset >= int(total):
                break
            if len(page) < PAGE_LIMIT:
                break
        return matches

    def normalize_fixture_payload(
        self,
        db: Session,
        item: dict,
        tournament_id: int,
        competition_type: str = "Cup",
    ) -> Optional[dict]:
        match_id = item.get("id")
        date_utc = _parse_date(item.get("date"))
        home_name, home_ext = _team_name(item, "home", "homeTeam")
        away_name, away_ext = _team_name(item, "away", "awayTeam")
        if match_id is None or not date_utc or not home_name or not away_name:
            return None

        team_type = "National" if competition_type == "International" else "Club"
        home_team = self.team_resolver.resolve(
            db,
            provider_name=PROVIDER_NAME,
            raw_name=home_name,
            external_id=home_ext,
            team_type=team_type,
        )
        away_team = self.team_resolver.resolve(
            db,
            provider_name=PROVIDER_NAME,
            raw_name=away_name,
            external_id=away_ext,
            team_type=team_type,
        )
        league = _league_name(item)
        stage = "League Phase" if league in LEAGUE_PHASE_NAMES else "Regular Season"
        status, home_score, away_score = _status_and_scores(item)
        return {
            "api_id": f"hl_{match_id}",
            "provider": PROVIDER_NAME,
            "provider_name": PROVIDER_NAME,
            "tournament_id": tournament_id,
            "home_team": home_team,
            "away_team": away_team,
            "date_utc": date_utc,
            "stage": stage,
            "status": status,
            "home_score": home_score,
            "away_score": away_score,
        }
