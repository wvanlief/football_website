from typing import List, Optional, Tuple
from sqlalchemy.orm import Session

from backend.database import Competition, Tournament, Fixture
from backend.scoring import score
from backend.services.ingestion.preflight import PreflightGuard
from backend.services.ingestion.team_resolver import TeamResolver
from backend.services.ingestion.fixture_upserter import FixtureUpserter, UpsertResult
from backend.services.ingestion.team_merge import merge_club_aliases
from backend.services.providers.football_data import FootballDataProvider
from backend.services.providers.openfootball import OpenFootballProvider
from backend.services.providers.thesportsdb import TheSportsDBProvider


class IngestionEngine:
    """
    Core Deep Ingestion Engine coordinating multi-provider fallback chains,
    pre-flight safety guards, team resolution, and fixture upserting.

    Guarantees:
    - Zero DELETE operations (strictly additive).
    - Pre-flight guard checks fetched fixture count against DB to prevent data loss.
    - Fallback chain: Football-Data.org -> openfootball -> TheSportsDB.
    """
    def __init__(
        self,
        preflight_guard: Optional[PreflightGuard] = None,
        team_resolver: Optional[TeamResolver] = None,
        fixture_upserter: Optional[FixtureUpserter] = None,
        fd_provider: Optional[FootballDataProvider] = None,
        openfootball_provider: Optional[OpenFootballProvider] = None,
        tsdb_provider: Optional[TheSportsDBProvider] = None,
    ):
        self.preflight = preflight_guard or PreflightGuard()
        self.team_resolver = team_resolver or TeamResolver()
        self.upserter = fixture_upserter or FixtureUpserter(team_resolver=self.team_resolver)
        self.fd_provider = fd_provider or FootballDataProvider(team_resolver=self.team_resolver)
        self.openfootball_provider = openfootball_provider or OpenFootballProvider(
            team_resolver=self.team_resolver
        )
        self.tsdb_provider = tsdb_provider or TheSportsDBProvider(
            team_resolver=self.team_resolver
        )
        self._fixture_request_skipped = False

    def _collect_raw_fixtures(
        self,
        competition_name: str,
        api_season: int,
    ) -> Tuple[List[dict], Optional[object], str]:
        fd_fixtures = self.fd_provider.fetch_fixtures(competition_name, api_season) or []
        fd_skipped = getattr(self.fd_provider, "last_request_skipped", False) is True
        self._fixture_request_skipped = fd_skipped
        if fd_fixtures:
            print(
                f"Ingestion: using Football-Data.org for {competition_name} "
                f"({len(fd_fixtures)} fixtures)."
            )
            self._fixture_request_skipped = False
            return fd_fixtures, self.fd_provider, "Football-Data.org"

        print(
            f"Ingestion: Football-Data.org returned no fixtures for {competition_name}; "
            f"trying openfootball."
        )
        of_fixtures = self.openfootball_provider.fetch_fixtures(competition_name, api_season) or []
        if of_fixtures:
            print(
                f"Ingestion: using openfootball for {competition_name} "
                f"({len(of_fixtures)} fixtures)."
            )
            return of_fixtures, self.openfootball_provider, "openfootball"

        print(
            f"Ingestion: openfootball returned no fixtures for {competition_name}; "
            f"trying TheSportsDB."
        )
        tsdb_fixtures = self.tsdb_provider.fetch_fixtures(competition_name, api_season) or []
        if tsdb_fixtures:
            print(
                f"Ingestion: using TheSportsDB for {competition_name} "
                f"({len(tsdb_fixtures)} fixtures)."
            )
            return tsdb_fixtures, self.tsdb_provider, "TheSportsDB"

        print(
            f"Ingestion: no fixtures from Football-Data.org, openfootball, "
            f"or TheSportsDB for {competition_name}."
        )
        return [], None, "none"

    def seed_competition(
        self,
        db: Session,
        competition_name: str,
        competition_type: str = "League",
        format_engine: str = "league",
        season: str = "2026/27",
        api_league_id: Optional[int] = None,
        api_season: int = 2026,
        badge: Optional[str] = None,
        home_advantage_elo: int = 100,
        odds_api_sport_key: Optional[str] = None
    ) -> UpsertResult:
        """
        Seeds or updates a competition using the multi-provider fallback chain.
        Creates Competition and Tournament entities if missing, runs pre-flight guard,
        and batch-upserts normalized fixture payloads.
        """
        merge_club_aliases(db, commit=False)

        # 1. Ensure Competition exists
        comp = db.query(Competition).filter(Competition.name == competition_name).first()
        if not comp:
            comp = Competition(
                name=competition_name,
                type=competition_type,
                format_engine=format_engine,
                badge=badge,
                api_league_id=api_league_id,
                odds_api_sport_key=odds_api_sport_key,
                home_advantage_elo=home_advantage_elo
            )
            db.add(comp)
            db.flush()
        else:
            if api_league_id:
                comp.api_league_id = api_league_id
            if odds_api_sport_key:
                comp.odds_api_sport_key = odds_api_sport_key

        # 2. Ensure Tournament exists
        tourney = db.query(Tournament).filter(
            Tournament.competition_id == comp.id,
            Tournament.season_name == season
        ).first()
        if not tourney:
            tourney = Tournament(
                competition_id=comp.id,
                season_name=season,
                status="Active"
            )
            db.add(tourney)
            db.flush()
        else:
            tourney.status = "Active"

        # 3. Provider Fallback Chain: Football-Data.org -> openfootball -> TheSportsDB
        raw_fixtures, provider, source_name = self._collect_raw_fixtures(
            competition_name, api_season
        )

        # 4. Run Pre-flight Safety Guard before team/fixture mutation
        self.preflight.check_fixture_count(db, tourney.id, len(raw_fixtures))

        normalized_fixtures = []
        if provider:
            for item in raw_fixtures:
                norm_item = provider.normalize_fixture_payload(
                    db, item, tourney.id, competition_type
                )
                if norm_item:
                    normalized_fixtures.append(norm_item)

        # 5. Batch Upsert Fixtures
        result = self.upserter.upsert_fixtures(db, tourney, normalized_fixtures, competition=comp)
        merge_club_aliases(db, commit=False)
        self._score_tournament_fixtures(db, tourney.id)
        if self._fixture_request_skipped:
            result.status = "skipped"
            result.message = "Football-Data.org fixture request was skipped"
        db.commit()
        print(
            f"Ingestion: upserted {result.created} created / {result.updated} updated "
            f"fixtures for {competition_name} from {source_name}."
        )
        return result

    def overlay_from_football_data(
        self,
        db: Session,
        tournament: Tournament,
        competition: Competition,
        api_season: int,
    ) -> UpsertResult:
        """Additive Football-Data.org overlay. Never falls back to other providers or DELETE."""
        if not getattr(self.fd_provider, "api_key", None):
            print(
                f"Overlay: skipped for {competition.name}; Football-Data.org key is not configured."
            )
            return UpsertResult(
                status="skipped",
                message="Football-Data.org key is not configured",
            )

        raw_fixtures = self.fd_provider.fetch_fixtures(competition.name, api_season) or []
        if not raw_fixtures:
            print(
                f"Overlay: Football-Data.org returned no fixtures for {competition.name}."
            )
            return UpsertResult(
                status="skipped",
                message="Football-Data.org returned no fixtures",
            )

        self.preflight.check_fixture_count(db, tournament.id, len(raw_fixtures))

        normalized_fixtures = []
        for item in raw_fixtures:
            norm_item = self.fd_provider.normalize_fixture_payload(
                db, item, tournament.id, competition.type or "Cup"
            )
            if not norm_item:
                continue
            if not norm_item.get("home_team") or not norm_item.get("away_team"):
                continue
            normalized_fixtures.append(norm_item)

        self.preflight.assert_no_deletes("overlay_from_football_data")
        result = self.upserter.upsert_fixtures(
            db, tournament, normalized_fixtures, competition=competition
        )
        merge_club_aliases(db, commit=False)
        self._score_tournament_fixtures(db, tournament.id)
        db.flush()
        print(
            f"Overlay: Football-Data.org stamped/inserted "
            f"{result.created} created / {result.updated} updated "
            f"fixtures for {competition.name}."
        )
        return result

    def _score_tournament_fixtures(self, db: Session, tournament_id: int) -> None:
        fixtures = (
            db.query(Fixture)
            .filter(Fixture.tournament_id == tournament_id)
            .all()
        )
        for fixture in fixtures:
            if fixture.home_team_id and fixture.away_team_id:
                score(fixture, db)

    def sync_tournament(self, db: Session, tournament: Tournament) -> UpsertResult:
        """
        Synchronizes ongoing fixtures for an existing tournament.
        """
        comp = tournament.competition
        season_year = 2026
        try:
            season_year = int(tournament.season_name.split("/")[0])
        except (ValueError, AttributeError):
            pass

        return self.seed_competition(
            db,
            competition_name=comp.name,
            competition_type=comp.type,
            format_engine=comp.format_engine,
            season=tournament.season_name,
            api_league_id=comp.api_league_id,
            api_season=season_year,
            badge=comp.badge,
            home_advantage_elo=comp.home_advantage_elo or 100,
            odds_api_sport_key=comp.odds_api_sport_key
        )


def seed_competition(
    db: Session,
    competition_name: str,
    competition_type: str = "League",
    format_engine: str = "league",
    season: str = "2026/27",
    api_league_id: Optional[int] = None,
    api_season: int = 2026,
    badge: Optional[str] = None,
    home_advantage_elo: int = 100,
    odds_api_sport_key: Optional[str] = None
) -> UpsertResult:
    """Public convenience function for seeding a competition."""
    engine = IngestionEngine()
    return engine.seed_competition(
        db,
        competition_name=competition_name,
        competition_type=competition_type,
        format_engine=format_engine,
        season=season,
        api_league_id=api_league_id,
        api_season=api_season,
        badge=badge,
        home_advantage_elo=home_advantage_elo,
        odds_api_sport_key=odds_api_sport_key
    )
