"""Knockout bracket propagation and placeholder resolution.

Write-path tournament progression: advancing winners/losers into later rounds
and turning fixture placeholders (e.g. ``Winner Match 78``) into readable labels.
"""
import re
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from backend.database import Fixture, FixtureDependency, FixtureOdds
from backend.services.odds import calculate_default_odds


NEXT_ROUND_LOOKUP = {
    73: (90, "home"), 74: (89, "home"), 75: (90, "away"), 76: (91, "home"),
    77: (89, "away"), 78: (91, "away"), 79: (92, "home"), 80: (92, "away"),
    81: (94, "home"), 82: (94, "away"), 83: (93, "home"), 84: (93, "away"),
    85: (96, "home"), 86: (95, "home"), 87: (96, "away"), 88: (95, "away"),
    89: (97, "home"), 90: (97, "away"), 91: (99, "home"), 92: (99, "away"),
    93: (98, "home"), 94: (98, "away"), 95: (100, "home"), 96: (100, "away"),
    97: (101, "home"), 98: (101, "away"), 99: (102, "home"), 100: (102, "away"),
    101: (104, "home"), 102: (104, "away")
}


def propagate_knockout_fixtures(db: Session):
    """
    Scans finished knockout fixtures in the database and propagates winners/losers
    to subsequent rounds using data-driven fixture_dependencies.
    """
    fixtures = db.query(Fixture).all()
    fixtures_by_id = {f.id: f for f in fixtures}
    fixtures_by_api_id = {f.api_id: f for f in fixtures if f.api_id}

    modified_fixtures = set()

    updated = True
    iterations = 0
    while updated and iterations < 10:
        updated = False
        iterations += 1

        for f in fixtures:
            if f.status != "Finished" or f.stage == "Group Stage" or f.stage == "Regular Season" or f.stage == "League Phase":
                continue

            if f.leg_number == 1:
                # Two-legged ties only propagate after leg 2 is played
                leg2 = db.query(Fixture).filter(
                    Fixture.tournament_id == f.tournament_id,
                    Fixture.stage == f.stage,
                    Fixture.leg_number == 2,
                    ((Fixture.home_team_id == f.away_team_id) & (Fixture.away_team_id == f.home_team_id)) |
                    ((Fixture.home_team_id == f.home_team_id) & (Fixture.away_team_id == f.away_team_id))
                ).first()
                if leg2:
                    continue

            winner_id = f.winner_id
            if not winner_id:
                if f.leg_number == 2:
                    # Find corresponding leg 1 fixture: opposite teams, leg 1, same tournament and stage
                    leg1 = db.query(Fixture).filter(
                        Fixture.tournament_id == f.tournament_id,
                        Fixture.stage == f.stage,
                        Fixture.home_team_id == f.away_team_id,
                        Fixture.away_team_id == f.home_team_id,
                        Fixture.leg_number == 1
                    ).first()
                    if leg1 and leg1.home_score is not None and leg1.away_score is not None and f.home_score is not None and f.away_score is not None:
                        agg_home = f.home_score + leg1.away_score
                        agg_away = f.away_score + leg1.home_score
                        if agg_home > agg_away:
                            winner_id = f.home_team_id
                        elif agg_home < agg_away:
                            winner_id = f.away_team_id
                        else:
                            if f.home_penalty_score is not None and f.away_penalty_score is not None:
                                winner_id = f.home_team_id if f.home_penalty_score > f.away_penalty_score else f.away_team_id
                else:
                    # Single-leg tie winner determination
                    if f.home_score is not None and f.away_score is not None:
                        if f.home_score > f.away_score:
                            winner_id = f.home_team_id
                        elif f.home_score < f.away_score:
                            winner_id = f.away_team_id
                        else:
                            if f.home_penalty_score is not None and f.away_penalty_score is not None:
                                winner_id = f.home_team_id if f.home_penalty_score > f.away_penalty_score else f.away_team_id

            if not winner_id:
                continue

            loser_id = f.away_team_id if winner_id == f.home_team_id else f.home_team_id

            dependencies = db.query(FixtureDependency).filter(FixtureDependency.source_fixture_id == f.id).all()

            if dependencies:
                # DB-driven propagation
                for dep in dependencies:
                    target_fixture = fixtures_by_id.get(dep.target_fixture_id)
                    if not target_fixture:
                        continue
                    prog_team_id = winner_id if dep.result_type == "winner" else loser_id
                    if not prog_team_id:
                        continue

                    if dep.slot == "home":
                        if target_fixture.home_team_id != prog_team_id:
                            target_fixture.home_team_id = prog_team_id
                            target_fixture.home_team_placeholder = None
                            updated = True
                            modified_fixtures.add(target_fixture)
                    elif dep.slot == "away":
                        if target_fixture.away_team_id != prog_team_id:
                            target_fixture.away_team_id = prog_team_id
                            target_fixture.away_team_placeholder = None
                            updated = True
                            modified_fixtures.add(target_fixture)
            else:
                # Backwards compatibility fallback to NEXT_ROUND_LOOKUP for World Cup
                if not f.api_id:
                    continue
                try:
                    match_num = int(f.api_id)
                except ValueError:
                    continue

                # 1. Standard next-round propagation
                next_info = NEXT_ROUND_LOOKUP.get(match_num)
                if next_info:
                    next_match_num, slot = next_info
                    next_fixture = fixtures_by_api_id.get(str(next_match_num))
                    if next_fixture:
                        if slot == "home":
                            if next_fixture.home_team_id != winner_id:
                                next_fixture.home_team_id = winner_id
                                next_fixture.home_team_placeholder = None
                                updated = True
                                modified_fixtures.add(next_fixture)
                        elif slot == "away":
                            if next_fixture.away_team_id != winner_id:
                                next_fixture.away_team_id = winner_id
                                next_fixture.away_team_placeholder = None
                                updated = True
                                modified_fixtures.add(next_fixture)

                # 2. Third-place play-off (api_id 103) is populated by the losers of match 101 and 102
                if match_num == 101:
                    third_fixture = fixtures_by_api_id.get("103")
                    if third_fixture and third_fixture.home_team_id != loser_id:
                        third_fixture.home_team_id = loser_id
                        third_fixture.home_team_placeholder = None
                        updated = True
                        modified_fixtures.add(third_fixture)
                elif match_num == 102:
                    third_fixture = fixtures_by_api_id.get("103")
                    if third_fixture and third_fixture.away_team_id != loser_id:
                        third_fixture.away_team_id = loser_id
                        third_fixture.away_team_placeholder = None
                        updated = True
                        modified_fixtures.add(third_fixture)

    if modified_fixtures:
        now_time = datetime.now(timezone.utc)
        for fixture in modified_fixtures:
            h_elo = fixture.home_team.elo if fixture.home_team else 1700
            a_elo = fixture.away_team.elo if fixture.away_team else 1700
            odds_h, odds_d, odds_a = calculate_default_odds(h_elo, a_elo)

            db_odds = FixtureOdds(
                fixture_id=fixture.id,
                recorded_at=now_time,
                odds_home=odds_h,
                odds_draw=odds_d,
                odds_away=odds_a
            )
            db.add(db_odds)


def resolve_placeholder_name(db: Session, placeholder: str, tournament_id: int) -> str:
    """
    Resolves a placeholder string (e.g., 'Winner Match 78') into a human-readable description.
    For match references, looks up the referenced fixture and returns participating team names.
    """
    if not placeholder:
        return "TBD"
    match_ref = re.search(r"Match (\d+)", placeholder)
    if match_ref:
        ref_api_id = match_ref.group(1)
        ref_fixture = db.query(Fixture).filter(
            Fixture.tournament_id == tournament_id,
            Fixture.api_id == ref_api_id
        ).first()
        if ref_fixture:
            h_name = ref_fixture.home_team.name if ref_fixture.home_team else ref_fixture.home_team_placeholder
            a_name = ref_fixture.away_team.name if ref_fixture.away_team else ref_fixture.away_team_placeholder
            if h_name and a_name:
                def simplify(name):
                    """Simplifies group placeholder labels by removing redundant text."""
                    return name.replace("Runner-up Group ", "Runner-up ").replace("Winner Group ", "Winner ")
                return f"{placeholder} ({simplify(h_name)} or {simplify(a_name)})"
    return placeholder
