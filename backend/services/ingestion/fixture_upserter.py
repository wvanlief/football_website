from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple, Any
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_

from backend.database import Fixture, FixtureOdds, Tournament, TournamentTeam, Competition
from backend.services.ingestion.team_resolver import TeamResolver
from backend.services.odds import calculate_default_odds
from backend.services.settling import settle_result


class UpsertResult:
    def __init__(self, created: int = 0, updated: int = 0, odds_added: int = 0):
        self.created = created
        self.updated = updated
        self.odds_added = odds_added

    def to_dict(self) -> dict:
        return {
            "created": self.created,
            "updated": self.updated,
            "odds_added": self.odds_added,
        }


class FixtureUpserter:
    """
    Unified fixture upserting engine.
    Strictly additive: creates or updates Fixture records without performing any DELETE operations.

    Features:
    - Matches existing fixtures by api_id or by (home_team_id, away_team_id) within ±12 hours.
    - Registers TournamentTeam associations when home/away teams are resolved.
    - Adds default FixtureOdds with date deduplication (no duplicate odds entries for the same date).
    - Settles finished fixtures using settle_result().
    """
    def __init__(self, team_resolver: Optional[TeamResolver] = None):
        self.team_resolver = team_resolver or TeamResolver()

    def upsert_fixture(
        self,
        db: Session,
        tournament: Tournament,
        fixture_payload: Dict[str, Any],
        competition: Optional[Competition] = None
    ) -> Tuple[Fixture, bool]:
        """
        Upserts a single fixture payload into the given tournament.
        Returns tuple of (Fixture, is_created: bool).
        """
        comp = competition or (tournament.competition if tournament else None)
        provider_name = fixture_payload.get("provider_name", "api_football")
        
        # 1. Resolve Home & Away teams if raw data provided
        home_team = fixture_payload.get("home_team")
        if not home_team and fixture_payload.get("home_team_name"):
            home_team = self.team_resolver.resolve(
                db,
                provider_name=provider_name,
                raw_name=fixture_payload["home_team_name"],
                external_id=fixture_payload.get("home_team_external_id"),
                team_type="National" if (comp and comp.type == "International") else "Club",
                api_id=fixture_payload.get("home_team_api_id")
            )

        away_team = fixture_payload.get("away_team")
        if not away_team and fixture_payload.get("away_team_name"):
            away_team = self.team_resolver.resolve(
                db,
                provider_name=provider_name,
                raw_name=fixture_payload["away_team_name"],
                external_id=fixture_payload.get("away_team_external_id"),
                team_type="National" if (comp and comp.type == "International") else "Club",
                api_id=fixture_payload.get("away_team_api_id")
            )

        # Register TournamentTeam relationships
        added_teams = set()
        for t in (home_team, away_team):
            if t and tournament and t.id not in added_teams:
                added_teams.add(t.id)
                tt = db.query(TournamentTeam).filter(
                    TournamentTeam.tournament_id == tournament.id,
                    TournamentTeam.team_id == t.id
                ).first()
                if not tt:
                    db.add(TournamentTeam(tournament_id=tournament.id, team_id=t.id))

        api_id = str(fixture_payload.get("api_id")) if fixture_payload.get("api_id") is not None else None
        date_utc = fixture_payload.get("date_utc") or datetime.now(timezone.utc)
        stage = fixture_payload.get("stage", "Group Stage")
        status = fixture_payload.get("status", "Scheduled")
        matchday = fixture_payload.get("matchday_number")

        # 2. Look up existing fixture
        fixture = None
        if api_id and tournament:
            fixture = db.query(Fixture).filter(
                Fixture.tournament_id == tournament.id,
                Fixture.api_id == api_id
            ).first()

        if not fixture and home_team and away_team and tournament:
            window_start = date_utc - timedelta(hours=12)
            window_end = date_utc + timedelta(hours=12)
            fixture = db.query(Fixture).filter(
                Fixture.tournament_id == tournament.id,
                Fixture.stage == stage,
                Fixture.date_utc >= window_start,
                Fixture.date_utc <= window_end,
                or_(
                    and_(Fixture.home_team_id == home_team.id, Fixture.away_team_id == away_team.id),
                    and_(Fixture.home_team_id == away_team.id, Fixture.away_team_id == home_team.id)
                )
            ).first()

        is_created = False
        feed_home_score = fixture_payload.get("home_score")
        feed_away_score = fixture_payload.get("away_score")

        if not fixture:
            fixture = Fixture(
                tournament_id=tournament.id if tournament else None,
                home_team_id=home_team.id if home_team else None,
                away_team_id=away_team.id if away_team else None,
                home_team_placeholder=fixture_payload.get("home_team_placeholder") or (fixture_payload.get("home_team_name") if not home_team else None),
                away_team_placeholder=fixture_payload.get("away_team_placeholder") or (fixture_payload.get("away_team_name") if not away_team else None),
                api_id=api_id,
                date_utc=date_utc,
                stage=stage,
                matchday_number=matchday,
                status=status,
                home_score=feed_home_score,
                away_score=feed_away_score,
                leg_number=fixture_payload.get("leg_number", 1)
            )
            db.add(fixture)
            db.flush()
            is_created = True
        else:
            # Update existing fixture fields safely
            if home_team and fixture.home_team_id is None:
                fixture.home_team_id = home_team.id
                fixture.home_team_placeholder = None
            if away_team and fixture.away_team_id is None:
                fixture.away_team_id = away_team.id
                fixture.away_team_placeholder = None

            if date_utc and fixture.date_utc != date_utc:
                fixture.date_utc = date_utc
            if matchday and fixture.matchday_number != matchday:
                fixture.matchday_number = matchday
            if api_id and not fixture.api_id:
                fixture.api_id = api_id

        # 3. Handle score settling or status updates
        if status == "Finished" or (feed_home_score is not None and feed_away_score is not None and status == "Finished"):
            settle_result(fixture, int(feed_home_score), int(feed_away_score))
        elif status == "Live":
            fixture.status = "Live"
            if feed_home_score is not None:
                fixture.home_score = int(feed_home_score)
            if feed_away_score is not None:
                fixture.away_score = int(feed_away_score)

        # 4. Add initial odds if creating or missing, using date deduplication
        self._ensure_fixture_odds(db, fixture, home_team, away_team, comp)

        return fixture, is_created

    def _ensure_fixture_odds(
        self,
        db: Session,
        fixture: Fixture,
        home_team: Optional[Any],
        away_team: Optional[Any],
        competition: Optional[Competition]
    ) -> bool:
        """
        Adds default odds for a fixture if no odds entry exists for the current date (date deduplication).
        Returns True if new odds row was added.
        """
        now_time = datetime.now(timezone.utc)
        record_date = now_time.date()

        # Check if an odds snapshot was already recorded for this fixture today
        existing = db.query(FixtureOdds).filter(
            FixtureOdds.fixture_id == fixture.id
        ).all()
        for o in existing:
            if o.recorded_at and o.recorded_at.date() == record_date:
                return False

        h_elo = home_team.elo if home_team and hasattr(home_team, "elo") else 1700
        a_elo = away_team.elo if away_team and hasattr(away_team, "elo") else 1700

        neutral = competition.neutral_venue if competition else True
        home_adv = (competition.home_advantage_elo or 100) if competition else 100

        odds_h, odds_d, odds_a = calculate_default_odds(h_elo, a_elo, neutral_venue=neutral, home_advantage=home_adv)

        init_odds = FixtureOdds(
            fixture_id=fixture.id,
            recorded_at=now_time,
            odds_home=odds_h,
            odds_draw=odds_d,
            odds_away=odds_a
        )
        db.add(init_odds)
        db.flush()
        return True

    def upsert_fixtures(
        self,
        db: Session,
        tournament: Tournament,
        fixture_payloads: List[Dict[str, Any]],
        competition: Optional[Competition] = None
    ) -> UpsertResult:
        """
        Batch upserts multiple fixture payloads. Returns UpsertResult summary.
        """
        created_count = 0
        updated_count = 0

        for payload in fixture_payloads:
            _, is_created = self.upsert_fixture(db, tournament, payload, competition=competition)
            if is_created:
                created_count += 1
            else:
                updated_count += 1

        db.flush()
        return UpsertResult(created=created_count, updated=updated_count)
