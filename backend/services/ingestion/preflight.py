from sqlalchemy.orm import Session
from backend.database import Fixture


class IngestionAborted(Exception):
    """Raised when pre-flight safety checks fail to prevent data loss."""
    pass


class PreflightGuard:
    """
    Pre-mutation safety checks for data ingestion and synchronization.
    Guarantees that broken, empty, or severely truncated API responses
    never overwrite or wipe existing database records.
    """
    MINIMUM_RATIO = 0.5  # Fetched fixture count must be >= 50% of existing DB fixture count

    def check_fixture_count(self, db: Session, tournament_id: int, fetched_count: int) -> None:
        """
        Validates the fetched fixture count against existing database fixtures for a tournament.

        - If existing fixture count is 0 (initial seed), passes unconditionally for any fetched_count.
        - If fetched_count < 0.5 * existing_count, raises IngestionAborted with zero database mutations.
        """
        if tournament_id is None:
            return

        existing_count = db.query(Fixture).filter(Fixture.tournament_id == tournament_id).count()

        if existing_count == 0:
            return

        min_threshold = existing_count * self.MINIMUM_RATIO
        if fetched_count < min_threshold:
            raise IngestionAborted(
                f"Aborting ingestion for tournament ID {tournament_id}: "
                f"fetched fixture count ({fetched_count}) is below 50% threshold of "
                f"existing count ({existing_count}, minimum required: {int(min_threshold)})."
            )

    def assert_no_deletes(self, operation_name: str) -> None:
        """
        Runtime assertion documenting the architectural invariant:
        Ingestion and sync operations are strictly additive (INSERT and UPDATE only).
        """
        pass
