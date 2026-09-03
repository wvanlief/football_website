"""Compatibility facade for tournament services.

The original monolith is split into:

- ``knockout.py`` — bracket propagation and placeholder resolution
- ``enrichment.py`` — fixture dict shaping and time-bucket grouping
- ``queries.py`` — API-facing query orchestration

Existing imports from ``backend.services.tournament`` continue to work.
"""
from backend.services.enrichment import (
    enrich_fixture,
    get_timezone,
    group_enriched_fixtures,
)
from backend.services.knockout import (
    NEXT_ROUND_LOOKUP,
    propagate_knockout_fixtures,
    resolve_placeholder_name,
)
from backend.services.queries import (
    evaluate_nations_league_promotions,
    get_all_third_placed_teams,
    get_calendar_fixtures,
    get_country_details,
    get_fixture_details_by_id,
    get_group_details,
    get_grouped_fixtures,
    get_recommended_fixtures,
    invalidate_fixtures_cache,
)
from backend.services.standings import (
    calculate_points_needed_to_guarantee_top_2,
    calculate_standings,
)

__all__ = [
    "NEXT_ROUND_LOOKUP",
    "calculate_points_needed_to_guarantee_top_2",
    "calculate_standings",
    "enrich_fixture",
    "evaluate_nations_league_promotions",
    "get_all_third_placed_teams",
    "get_calendar_fixtures",
    "get_country_details",
    "get_fixture_details_by_id",
    "get_group_details",
    "get_grouped_fixtures",
    "get_recommended_fixtures",
    "get_timezone",
    "group_enriched_fixtures",
    "invalidate_fixtures_cache",
    "propagate_knockout_fixtures",
    "resolve_placeholder_name",
]
