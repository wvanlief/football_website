"""TheSportsDB v1 provider — tertiary fixture fallback (ADR-0002)."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set
from urllib.parse import urlencode

from sqlalchemy.orm import Session

from backend.utils import fetch_json_with_retry
from backend.services.ingestion.normalizer import NameNormalizer
from backend.services.ingestion.team_resolver import TeamResolver

PROVIDER_NAME = "thesportsdb"
BASE_URL = "https://www.thesportsdb.com/api/v1/json"
FREE_API_KEY = "123"

# Canonical competition names → TheSportsDB idLeague.
# Europa League (4481) and Conference League (5071) are the cups Football-Data.org
# free plan and openfootball 2026/27 datasets do not cover.
LEAGUE_ID_MAP: Dict[str, str] = {
    "Premier League": "4328",
    "EFL Championship": "4329",
    "Scottish Premiership": "4330",
    "Bundesliga": "4331",
    "Serie A": "4332",
    "Ligue 1": "4334",
    "La Liga": "4335",
    "Eredivisie": "4337",
    "Belgian Pro League": "4338",
    "Süper Lig": "4339",
    "Primeira Liga": "4344",
    "Major League Soccer": "4346",
    "Brasileirão Série A": "4351",
    "FIFA World Cup": "4429",
    "UEFA Champions League": "4480",
    "UEFA Europa League": "4481",
    "FA Cup": "4482",
    "Copa del Rey": "4483",
    "Coupe de France": "4484",
    "DFB Pokal": "4485",
    "UEFA Nations League": "4490",
    "Copa Argentina": "4500",
    "Copa Libertadores": "4501",
    "European Championship": "4502",
    "Coppa Italia": "4506",
    "Taça de Portugal": "4510",
    "EFL Cup": "4570",
    "Liga Profesional Argentina": "4406",
    "CONCACAF Champions Cup": "4721",
    "Copa Sudamericana": "4724",
    "Copa do Brasil": "4725",
    "KNVB Beker": "4902",
    "UEFA Conference League": "5071",
}

CALENDAR_YEAR_COMPETITIONS: Set[str] = {
    "Major League Soccer",
    "Brasileirão Série A",
    "Copa do Brasil",
    "Liga Profesional Argentina",
    "Copa Argentina",
    "Copa Libertadores",
    "Copa Sudamericana",
    "CONCACAF Champions Cup",
    "FIFA World Cup",
}

STATUS_MAP = {
    "FT": "Finished",
    "AET": "Finished",
    "PEN": "Finished",
    "Match Finished": "Finished",
    "1H": "Live",
    "2H": "Live",
    "HT": "Live",
    "ET": "Live",
    "P": "Live",
    "LIVE": "Live",
    "Not Started": "Scheduled",
    "NS": "Scheduled",
    "TBD": "Scheduled",
    "Postponed": "Postponed",
    "Cancelled": "Postponed",
    "Canceled": "Postponed",
    "Abandoned": "Postponed",
    "PST": "Postponed",
    "CANC": "Postponed",
    "ABD": "Postponed",
}


def parse_event_status(raw_status: Optional[str], postponed: Optional[str] = None) -> str:
    """Map a TheSportsDB event status onto the domain status string."""
    if postponed and str(postponed).strip().lower() == "yes":
        return "Postponed"
    if not raw_status:
        return "Scheduled"
    return STATUS_MAP.get(raw_status, "Scheduled")


def parse_event_datetime(item: dict) -> Optional[datetime]:
    """Parse UTC kickoff from strTimestamp, else dateEvent + strTime."""
    timestamp = item.get("strTimestamp")
    if timestamp:
        try:
            dt = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            pass

    date_str = item.get("dateEvent")
    if not date_str:
        return None
    time_str = item.get("strTime") or "12:00:00"
    try:
        return datetime.fromisoformat(f"{date_str}T{time_str}+00:00")
    except Exception:
        try:
            return datetime.fromisoformat(str(date_str)).replace(tzinfo=timezone.utc)
        except Exception:
            return None


def parse_score(value) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def season_string(competition_name: str, season: int) -> str:
    """TheSportsDB season query: calendar year or split `YYYY-YYYY+1`."""
    if competition_name in CALENDAR_YEAR_COMPETITIONS:
        return str(season)
    return f"{season}-{season + 1}"


class TheSportsDBProvider:
    """
    Provider client for TheSportsDB (v1 JSON API).
    Fetches season events, normalizes domain fixtures, and links teams
    through ExternalTeamMapping via TeamResolver.
    """

    def __init__(self, api_key: Optional[str] = None, team_resolver: Optional[TeamResolver] = None):
        self.api_key = api_key or os.getenv("THESPORTSDB_API_KEY") or FREE_API_KEY
        self.normalizer = NameNormalizer()
        self.team_resolver = team_resolver or TeamResolver(self.normalizer)

    def get_league_id(self, competition_name: str) -> Optional[str]:
        return LEAGUE_ID_MAP.get(competition_name)

    def call_api(self, endpoint: str, params: Optional[dict] = None) -> dict:
        query = f"?{urlencode(params)}" if params else ""
        url = f"{BASE_URL}/{self.api_key}/{endpoint}{query}"
        return fetch_json_with_retry(
            url,
            headers={"User-Agent": "Mozilla/5.0"},
            provider=PROVIDER_NAME,
        )

    def fetch_fixtures(self, competition_name: str, season: int) -> List[dict]:
        league_id = self.get_league_id(competition_name)
        if not league_id:
            print(f"TheSportsDB: Competition '{competition_name}' is not in the league ID map.")
            return []

        season_s = season_string(competition_name, season)
        try:
            res = self.call_api("eventsseason.php", {"id": league_id, "s": season_s})
            if not isinstance(res, dict):
                return []
            events = res.get("events") or []
            if not isinstance(events, list):
                return []
            return [
                item for item in events
                if str(item.get("idLeague") or "") == str(league_id)
            ]
        except Exception as exc:
            print(f"TheSportsDB API error fetching fixtures for {competition_name}: {exc}")
            return []

    def fetch_teams(self, competition_name: str, season: int) -> List[dict]:
        league_id = self.get_league_id(competition_name)
        if not league_id:
            return []
        try:
            res = self.call_api("lookup_all_teams.php", {"id": league_id})
            if not isinstance(res, dict):
                return []
            return res.get("teams") or []
        except Exception as exc:
            print(f"TheSportsDB API error fetching teams for {competition_name}: {exc}")
            return []

    def normalize_fixture_payload(
        self,
        db: Session,
        item: dict,
        tournament_id: int,
        competition_type: str = "League",
    ) -> Optional[dict]:
        date_utc = parse_event_datetime(item)
        if not date_utc:
            return None

        home_name = item.get("strHomeTeam") or ""
        away_name = item.get("strAwayTeam") or ""
        if not home_name or not away_name:
            return None

        team_type = "National" if competition_type == "International" else "Club"
        home_team = self.team_resolver.resolve(
            db,
            provider_name=PROVIDER_NAME,
            raw_name=home_name,
            external_id=item.get("idHomeTeam"),
            team_type=team_type,
            logo_url=item.get("strHomeTeamBadge"),
        )
        away_team = self.team_resolver.resolve(
            db,
            provider_name=PROVIDER_NAME,
            raw_name=away_name,
            external_id=item.get("idAwayTeam"),
            team_type=team_type,
            logo_url=item.get("strAwayTeamBadge"),
        )

        raw_round = parse_score(item.get("intRound"))
        if raw_round is not None and raw_round >= 400:
            stage = "Qualifying"
            matchday = None
        elif raw_round is not None and 1 <= raw_round <= 50:
            stage = "Regular Season"
            matchday = raw_round
        else:
            stage = "Regular Season"
            matchday = raw_round

        event_id = item.get("idEvent")
        if event_id is None:
            return None

        status = parse_event_status(item.get("strStatus"), item.get("strPostponed"))
        home_score = parse_score(item.get("intHomeScore"))
        away_score = parse_score(item.get("intAwayScore"))
        if status == "Finished" and (home_score is None or away_score is None):
            status = "Live" if home_score is not None or away_score is not None else "Scheduled"

        return {
            "api_id": f"tsdb_{event_id}",
            "raw_id": str(event_id),
            "provider": PROVIDER_NAME,
            "provider_name": PROVIDER_NAME,
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
