"""Highlightly fixtures: a season dump for the seeder, and a date-page failover for the daily updater."""
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
MAX_SEASON_PAGES = 8

LEAGUE_PHASE_NAMES = {
    "UEFA Europa League",
    "UEFA Conference League",
    "UEFA Europa Conference League",
}

# Highlightly's leagueName does not always match our catalog name.
SEASON_LEAGUE_ALIASES = {
    "UEFA Conference League": ["UEFA Europa Conference League"],
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


def season_query_names(competition_name: str) -> list[str]:
    names = [competition_name]
    for alias in SEASON_LEAGUE_ALIASES.get(competition_name, []):
        if alias not in names:
            names.append(alias)
    return names


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
    """Season dump for seeding, and a date query for the daily updater."""

    def __init__(self, api_key: Optional[str] = None, team_resolver: Optional[TeamResolver] = None):
        self.api_key = api_key if api_key is not None else get_highlightly_api_key()
        self.team_resolver = team_resolver or TeamResolver()

    def fetch_fixtures(self, competition_name: str, season: int, league_id: Optional[int] = None) -> list[dict]:
        """One or more ``GET /matches?leagueName=&season=`` pages. ``league_id`` is unused."""
        del league_id
        if not self.api_key:
            print(f"Highlightly: HIGHLIGHTLY_API_KEY is not set; skipping {competition_name}.")
            return []
        for league_name in season_query_names(competition_name):
            rows, failed = self._collect_pages(
                {"leagueName": league_name, "season": season},
                MAX_SEASON_PAGES,
                f"{competition_name} season {season} ({league_name})",
            )
            if rows:
                return rows
            if failed:
                return []
        print(f"Highlightly: no season fixtures for {competition_name} season {season}.")
        return []

    def fetch_matches_by_date(
        self,
        match_date: str,
        league_name: Optional[str] = None,
    ) -> list[dict]:
        if not self.api_key:
            return []
        params = {"date": match_date}
        if league_name:
            params["leagueName"] = league_name
        rows, _failed = self._collect_pages(params, MAX_PAGES, f"date {match_date}")
        return rows

    def _collect_pages(self, base_params: dict, max_pages: int, label: str) -> tuple[list[dict], bool]:
        """Return ``(matches, failed)``. ``failed`` is a transport or HTTP error."""
        matches: list[dict] = []
        offset = 0
        total = None
        for _page in range(max_pages):
            params = dict(base_params)
            params["limit"] = PAGE_LIMIT
            params["offset"] = offset
            page, total, failed = self._request_page(params, label)
            if failed:
                return matches, True
            if not page:
                break
            matches.extend(page)
            offset += PAGE_LIMIT
            if total is not None and offset >= int(total):
                break
            if len(page) < PAGE_LIMIT:
                break
        if total is not None and offset < int(total):
            print(f"Highlightly: stopped at {len(matches)} of {total} for {label}.")
        return matches, False

    def _request_page(self, params: dict, label: str) -> tuple[list[dict], Optional[int], bool]:
        url = f"{BASE_URL}/matches?{urlencode(params)}"
        try:
            payload = fetch_json_with_retry(
                url,
                headers={"x-rapidapi-key": self.api_key},
                use_cache=False,
                provider="highlightly",
            )
        except Exception as exc:
            print(f"Highlightly error for {label}: {exc}")
            return [], None, True
        if not isinstance(payload, dict):
            return [], None, True
        page = payload.get("data") or []
        if not isinstance(page, list):
            return [], None, True
        total = (payload.get("pagination") or {}).get("totalCount")
        if not page:
            plan = payload.get("plan") if isinstance(payload.get("plan"), dict) else None
            detail = payload.get("errors") or payload.get("error") or (plan or {}).get("message")
            if detail:
                print(f"Highlightly: no matches for {label} ({detail}).")
        return page, total, False

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
