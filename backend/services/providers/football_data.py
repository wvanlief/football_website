import os
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session

from backend.utils import fetch_json_with_retry
from backend.services.ingestion import NameNormalizer
from backend.services.ingestion.team_resolver import TeamResolver
from backend.crud.mapping import (
    get_team_by_external_id,
    get_competition_by_external_id,
    link_competition_external_id
)
from backend.database import Team, Competition, Fixture
from backend.services.lifecycle import finish_fixture

PROVIDER_NAME = "football_data"

# Canonical env var first; remaining names are read fallbacks during cutover.
FOOTBALL_DATA_ORG_KEY_ENV_VARS = (
    "FOOTBALL_DATA_ORG_KEY",
    "FOOTBALL_DATA_API_KEY",
    "FOOTBALL_DATA_KEY",
)


def get_football_data_org_key() -> Optional[str]:
    """Return the Football-Data.org token, preferring ``FOOTBALL_DATA_ORG_KEY``."""
    for name in FOOTBALL_DATA_ORG_KEY_ENV_VARS:
        value = os.getenv(name)
        if value:
            return value
    return None

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
    "Brasileirão Série A": "BSA",
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
    "LEAGUE_STAGE": "League Phase",
    "LEAGUE_PHASE": "League Phase",
    "LEAGUE": "League Phase",
    "PLAYOFFS": "Play-offs",
    "PLAY_OFF_ROUND": "Play-offs",
    "LAST_16": "Round of 16",
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
    def __init__(self, api_key: Optional[str] = None, team_resolver: Optional[TeamResolver] = None):
        self.api_key = api_key or get_football_data_org_key()
        self.normalizer = NameNormalizer()
        self.team_resolver = team_resolver or TeamResolver(self.normalizer)
        self.last_request_skipped = False

    def get_headers(self) -> Dict[str, str]:
        headers = {"User-Agent": "Mozilla/5.0"}
        if self.api_key:
            headers["X-Auth-Token"] = self.api_key
        return headers

    def call_api(self, endpoint: str, params: Optional[dict] = None, use_cache: bool = True) -> dict:
        query = ""
        if params:
            query = "?" + "&".join(f"{k}={v}" for k, v in params.items())
        url = f"https://api.football-data.org/v4/{endpoint}{query}"
        return fetch_json_with_retry(
            url,
            headers=self.get_headers(),
            use_cache=use_cache,
            provider="football_data_org",
            raise_on_rate_limit=True,
        )

    def get_competition_code(self, competition_name: str) -> Optional[str]:
        return COMPETITION_CODE_MAP.get(competition_name)

    def fetch_matches(self, date_from: str, date_to: str) -> List[dict]:
        """Fetch matches across covered competitions for a closed date range.

        Results and live-score sync must not use HTTP cache: scores change
        throughout the day.
        """
        try:
            res = self.call_api(
                "matches",
                {"dateFrom": date_from, "dateTo": date_to},
                use_cache=False,
            )
            if not isinstance(res, dict) or "matches" not in res:
                return []
            return res.get("matches", [])
        except Exception as e:
            print(f"Football-Data.org API error fetching matches {date_from}..{date_to}: {e}")
            return []

    def fetch_fixtures(
        self,
        competition_name: str,
        season: int,
        use_cache: bool = True,
    ) -> List[dict]:
        self.last_request_skipped = False
        code = self.get_competition_code(competition_name)
        if not code:
            print(f"Football-Data.org: Competition '{competition_name}' not mapped to a code.")
            return []
        
        try:
            res = self.call_api(
                f"competitions/{code}/matches",
                {"season": season},
                use_cache=use_cache,
            )
            if not isinstance(res, dict) or "matches" not in res:
                return []
            return res.get("matches", [])
        except RuntimeError as e:
            self.last_request_skipped = True
            print(f"Football-Data.org API call skipped for {competition_name}: {e}")
            return []
        except Exception as e:
            print(f"Football-Data.org API error fetching fixtures for {competition_name}: {e}")
            return []

    def fetch_teams(self, competition_name: str, season: int) -> List[dict]:
        self.last_request_skipped = False
        code = self.get_competition_code(competition_name)
        if not code:
            return []
        try:
            res = self.call_api(f"competitions/{code}/teams", {"season": season})
            if not isinstance(res, dict) or "teams" not in res:
                return []
            return res.get("teams", [])
        except RuntimeError as e:
            self.last_request_skipped = True
            print(f"Football-Data.org API call skipped for teams in {competition_name}: {e}")
            return []
        except Exception as e:
            print(f"Football-Data.org API error fetching teams for {competition_name}: {e}")
            return []

    def resolve_team(
        self,
        db: Session,
        raw_team_info: dict,
        team_type: str = "Club",
        default_elo: int = 1500,
        elo_source: Optional[str] = None,
    ) -> Optional[Team]:
        """
        Resolves a raw Football-Data team dict through TeamResolver:
        mapping tables, NameNormalizer, then create. Stores crest URLs on logo_url.
        """
        ext_id = str(raw_team_info.get("id")) if raw_team_info.get("id") is not None else None
        official_name = raw_team_info.get("name") or ""
        short_name = raw_team_info.get("shortName") or ""
        raw_name = official_name or short_name
        alt_names = [short_name] if short_name and short_name != raw_name else []
        area = raw_team_info.get("area") or {}
        country = area.get("name") if isinstance(area, dict) else None
        country_code = self.normalizer.get_country_code(country) if country else None
        crest = raw_team_info.get("crest") or None

        return self.team_resolver.resolve(
            db,
            provider_name=PROVIDER_NAME,
            raw_name=raw_name,
            external_id=ext_id,
            team_type=team_type,
            default_elo=default_elo,
            country_code=country_code,
            logo_url=crest,
            elo_source=elo_source,
            alt_names=alt_names,
        )

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


def match_status(raw_status: Optional[str]) -> str:
    """Map a Football-Data.org match status onto the domain status string."""
    if not raw_status:
        return "Scheduled"
    return STATUS_MAP.get(raw_status, "Scheduled")


def extract_match_scores(item: dict) -> Tuple[Optional[int], Optional[int]]:
    """Read current or full-time scores from a Football-Data.org match payload."""
    score = item.get("score") or {}
    partial = (None, None)
    for key in ("fullTime", "regularTime", "halfTime"):
        block = score.get(key) or {}
        home = block.get("home")
        away = block.get("away")
        if home is not None and away is not None:
            return home, away
        if partial == (None, None) and (home is not None or away is not None):
            partial = (home, away)
    return partial


def _parse_match_dt(item: dict) -> Optional[datetime]:
    utc = item.get("utcDate")
    if not utc:
        return None
    try:
        return datetime.fromisoformat(str(utc).replace("Z", "+00:00"))
    except Exception:
        return None


def _find_team_for_sync(db: Session, raw: dict, teams: List[Team], normalizer: NameNormalizer) -> Optional[Team]:
    ext_id = raw.get("id")
    if ext_id is not None:
        mapped = get_team_by_external_id(db, PROVIDER_NAME, str(ext_id))
        if mapped:
            return mapped
    names = [raw.get("name"), raw.get("shortName")]
    for name in names:
        if not name:
            continue
        norm = normalizer.normalize(name)
        for team in teams:
            if team.name == norm:
                return team
    for name in names:
        if not name:
            continue
        for team in teams:
            if normalizer.match_names(team.name, name):
                return team
    return None


def _incoming_competition_code(item: dict) -> Optional[str]:
    competition = item.get("competition") or {}
    code = competition.get("code")
    if code:
        return str(code)
    name = competition.get("name")
    if name:
        return COMPETITION_CODE_MAP.get(name)
    return None


def _fixture_competition_code(fixture: Fixture) -> Optional[str]:
    competition = fixture.tournament.competition if (fixture.tournament and fixture.tournament.competition) else None
    if not competition:
        return None
    return COMPETITION_CODE_MAP.get(competition.name)


def _stamp_provider_api_id(fixture: Fixture, match_id) -> None:
    if match_id is None:
        return
    prefixed = f"fd_{match_id}"
    if fixture.api_id == prefixed:
        return
    if not fixture.api_id or not str(fixture.api_id).startswith("fd_"):
        fixture.api_id = prefixed


def find_fixture_for_match(
    db: Session,
    item: dict,
    teams: List[Team],
    normalizer: NameNormalizer,
    tournament_id: Optional[int] = None,
) -> Optional[Fixture]:
    """Locate an existing fixture for a Football-Data.org match without creating rows."""
    query = db.query(Fixture)
    if tournament_id is not None:
        query = query.filter(Fixture.tournament_id == tournament_id)

    match_id = item.get("id")
    if match_id is not None:
        fixture = query.filter(Fixture.api_id == f"fd_{match_id}").first()
        if fixture:
            return fixture

        raw_id_candidates = query.filter(Fixture.api_id == str(match_id)).all()
        incoming_code = _incoming_competition_code(item)
        for candidate in raw_id_candidates:
            expected_code = _fixture_competition_code(candidate)
            if tournament_id is not None:
                if incoming_code and expected_code and incoming_code != expected_code:
                    continue
                return candidate
            if incoming_code and expected_code == incoming_code:
                return candidate

    home_team = _find_team_for_sync(db, item.get("homeTeam") or {}, teams, normalizer)
    away_team = _find_team_for_sync(db, item.get("awayTeam") or {}, teams, normalizer)
    if not home_team or not away_team:
        return None

    match_dt = _parse_match_dt(item)
    candidates_q = query.filter(
        Fixture.home_team_id == home_team.id,
        Fixture.away_team_id == away_team.id,
    )
    if match_dt is not None:
        window_start = match_dt - timedelta(hours=12)
        window_end = match_dt + timedelta(hours=12)
        dated = []
        for cand in candidates_q.all():
            if not cand.date_utc:
                continue
            cand_dt = cand.date_utc
            if cand_dt.tzinfo is None:
                cand_dt = cand_dt.replace(tzinfo=timezone.utc)
            if window_start <= cand_dt <= window_end:
                dated.append(cand)
        candidates = dated
    else:
        candidates = candidates_q.all()

    incoming_code = _incoming_competition_code(item)
    for cand in candidates:
        expected_code = _fixture_competition_code(cand)
        if tournament_id is not None:
            if incoming_code and expected_code and incoming_code != expected_code:
                continue
            return cand
        if incoming_code is not None and expected_code == incoming_code:
            return cand
    return None


def apply_matches_to_existing_fixtures(
    db: Session,
    matches: List[dict],
    tournament_id: Optional[int] = None,
) -> Tuple[int, int]:
    """Write date, scores, and statuses from Football-Data.org matches onto existing fixtures.

    Returns ``(non_finished_updates, finished_count)``. Never creates fixture rows.
    """
    if not matches:
        return 0, 0

    normalizer = NameNormalizer()
    teams = db.query(Team).all()
    updated = 0
    finished = 0

    for item in matches:
        fixture = find_fixture_for_match(db, item, teams, normalizer, tournament_id=tournament_id)
        if not fixture:
            continue

        new_status = match_status(item.get("status"))
        home_goals, away_goals = extract_match_scores(item)
        _stamp_provider_api_id(fixture, item.get("id"))

        match_dt = _parse_match_dt(item)
        date_changed = False
        if match_dt is not None:
            stored = fixture.date_utc
            if stored is not None and stored.tzinfo is None:
                stored = stored.replace(tzinfo=timezone.utc)
            if stored != match_dt:
                fixture.date_utc = match_dt
                date_changed = True

        if new_status == "Finished":
            if (
                fixture.status != "Finished"
                or fixture.home_score != home_goals
                or fixture.away_score != away_goals
            ):
                final_home = home_goals if home_goals is not None else fixture.home_score
                final_away = away_goals if away_goals is not None else fixture.away_score
                finish_fixture(fixture, final_home, final_away, db, update_standings=False)
                finished += 1
            continue

        changed = date_changed
        if fixture.status != new_status:
            fixture.status = new_status
            changed = True
        if home_goals is not None and fixture.home_score != home_goals:
            fixture.home_score = home_goals
            changed = True
        if away_goals is not None and fixture.away_score != away_goals:
            fixture.away_score = away_goals
            changed = True
        if changed:
            updated += 1

    return updated, finished
