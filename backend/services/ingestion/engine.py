from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session

from backend.database import Competition, Tournament
from backend.services.ingestion.preflight import PreflightGuard, IngestionAborted
from backend.services.ingestion.team_resolver import TeamResolver
from backend.services.ingestion.fixture_upserter import FixtureUpserter, UpsertResult
from backend.services.providers.football_data import FootballDataProvider
from backend.services.providers.api_football import ApiFootballProvider


class IngestionEngine:
    """
    Core Deep Ingestion Engine coordinating multi-provider fallback chains,
    pre-flight safety guards, team resolution, and fixture upserting.
    
    Guarantees:
    - Zero DELETE operations (strictly additive).
    - Pre-flight guard checks fetched fixture count against DB to prevent data loss.
    - Fallback chain: Football-Data.org -> API-Football.
    """
    def __init__(
        self,
        preflight_guard: Optional[PreflightGuard] = None,
        team_resolver: Optional[TeamResolver] = None,
        fixture_upserter: Optional[FixtureUpserter] = None,
        fd_provider: Optional[FootballDataProvider] = None,
        api_football_provider: Optional[ApiFootballProvider] = None,
    ):
        self.preflight = preflight_guard or PreflightGuard()
        self.team_resolver = team_resolver or TeamResolver()
        self.upserter = fixture_upserter or FixtureUpserter(team_resolver=self.team_resolver)
        self.fd_provider = fd_provider or FootballDataProvider()
        self.api_football_provider = api_football_provider or ApiFootballProvider()

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

        # 3. Provider Fallback Chain: Football-Data.org -> API-Football
        normalized_fixtures = []

        # Attempt Primary: Football-Data.org
        fd_fixtures = self.fd_provider.fetch_fixtures(competition_name, api_season)
        if fd_fixtures:
            for item in fd_fixtures:
                norm_item = self.fd_provider.normalize_fixture_payload(db, item, tourney.id, competition_type)
                if norm_item:
                    normalized_fixtures.append(norm_item)

        # Attempt Secondary: API-Football (if primary yielded no fixtures)
        if not normalized_fixtures and api_league_id:
            raw_af_fixtures = self.api_football_provider.fetch_fixtures(api_league_id, api_season)
            if raw_af_fixtures:
                for item in raw_af_fixtures:
                    norm_item = self.api_football_provider.normalize_fixture_payload(item)
                    if norm_item:
                        normalized_fixtures.append(norm_item)

        # 4. Run Pre-flight Safety Guard
        self.preflight.check_fixture_count(db, tourney.id, len(normalized_fixtures))

        # 5. Batch Upsert Fixtures
        result = self.upserter.upsert_fixtures(db, tourney, normalized_fixtures, competition=comp)
        db.commit()
        return result

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
