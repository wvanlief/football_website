"""openfootball/football.json community dataset provider."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from backend.utils import fetch_json_with_retry
from backend.services.ingestion.normalizer import NameNormalizer
from backend.services.ingestion.team_resolver import TeamResolver

PROVIDER_NAME = "openfootball"
GITHUB_RAW_BASE = "https://raw.githubusercontent.com/openfootball/football.json/master"

# Datasets that repo actually publishes for the active season.
# european → {season}-{season+1[-2:]}/{code}.json; calendar → {season}/{code}.json.
# There is no Champions League path.
OPENFOOTBALL_DATASETS: Dict[str, Tuple[str, str]] = {
    "Premier League": ("european", "en.1"),
    "EFL Championship": ("european", "en.2"),
    "Bundesliga": ("european", "de.1"),
    "La Liga": ("european", "es.1"),
    "Serie A": ("european", "it.1"),
    "Ligue 1": ("european", "fr.1"),
    "Eredivisie": ("european", "nl.1"),
    "Primeira Liga": ("european", "pt.1"),
    "Brasileirão Série A": ("calendar", "br.1"),
}


def _parse_score(score) -> Tuple[Optional[int], Optional[int]]:
    if score is None:
        return None, None
    if isinstance(score, dict):
        ft = score.get("ft")
        if isinstance(ft, (list, tuple)) and len(ft) >= 2:
            return ft[0], ft[1]
        return None, None
    if isinstance(score, (list, tuple)) and len(score) >= 2:
        return score[0], score[1]
    return None, None


class OpenFootballProvider:
    """Normalizes public-domain football.json payloads into domain fixture dicts."""

    def __init__(self, team_resolver: Optional[TeamResolver] = None):
        self.normalizer = NameNormalizer()
        self.team_resolver = team_resolver or TeamResolver(self.normalizer)

    def dataset_for(self, competition_name: str) -> Optional[Tuple[str, str]]:
        return OPENFOOTBALL_DATASETS.get(competition_name)

    def dataset_path(self, competition_name: str, season: int) -> Optional[str]:
        spec = self.dataset_for(competition_name)
        if not spec:
            return None
        kind, code = spec
        if kind == "calendar":
            return f"{season}/{code}.json"
        return f"{season}-{str(season + 1)[-2:]}/{code}.json"

    def fetch_fixtures(self, competition_name: str, season: int) -> List[dict]:
        rel_path = self.dataset_path(competition_name, season)
        if not rel_path:
            print(
                f"openfootball: Competition '{competition_name}' is not in the published coverage map."
            )
            return []

        url = f"{GITHUB_RAW_BASE}/{rel_path}"
        try:
            res = fetch_json_with_retry(
                url,
                headers={"User-Agent": "Mozilla/5.0"},
                provider="openfootball",
            )
            if not isinstance(res, dict) or "matches" not in res:
                return []
            return res.get("matches") or []
        except Exception as exc:
            print(f"openfootball error fetching fixtures for {competition_name}: {exc}")
            return []

    def normalize_fixture_payload(
        self,
        db: Session,
        item: dict,
        tournament_id: int,
        competition_type: str = "League",
    ) -> Optional[dict]:
        date_str = item.get("date")
        if not date_str:
            return None
        time_str = item.get("time") or "12:00"
        try:
            date_utc = datetime.fromisoformat(f"{date_str}T{time_str}:00+00:00")
        except Exception:
            try:
                date_utc = datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)
            except Exception:
                return None

        home_name = item.get("team1") or ""
        away_name = item.get("team2") or ""
        if not home_name or not away_name:
            return None

        team_type = "National" if competition_type == "International" else "Club"
        home_team = self.team_resolver.resolve(
            db,
            provider_name=PROVIDER_NAME,
            raw_name=home_name,
            external_id=home_name,
            team_type=team_type,
        )
        away_team = self.team_resolver.resolve(
            db,
            provider_name=PROVIDER_NAME,
            raw_name=away_name,
            external_id=away_name,
            team_type=team_type,
        )

        home_score, away_score = _parse_score(item.get("score"))
        status = "Finished" if home_score is not None and away_score is not None else "Scheduled"

        round_str = item.get("round") or ""
        matchday = None
        matchday_match = re.search(r"(\d+)", round_str)
        if matchday_match:
            matchday = int(matchday_match.group(1))

        slug_home = self.normalizer.normalize(home_name).replace(" ", "_")
        slug_away = self.normalizer.normalize(away_name).replace(" ", "_")
        api_id = f"of_{date_str}_{slug_home}_{slug_away}"

        return {
            "api_id": api_id,
            "provider_name": PROVIDER_NAME,
            "provider": PROVIDER_NAME,
            "tournament_id": tournament_id,
            "home_team": home_team,
            "away_team": away_team,
            "home_team_id": home_team.id if home_team else None,
            "away_team_id": away_team.id if away_team else None,
            "date_utc": date_utc,
            "stage": "Regular Season",
            "matchday_number": matchday,
            "status": status,
            "home_score": home_score,
            "away_score": away_score,
        }
