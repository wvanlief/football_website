from backend.database import Team, ExternalTeamMapping
from backend.services.ingestion.team_resolver import TeamResolver


def test_resolve_creates_new_team(db_session):
    """Resolving an unmapped, non-existent team creates a new Team entity and links ExternalTeamMapping."""
    resolver = TeamResolver()
    team = resolver.resolve(
        db=db_session,
        provider_name="football_data",
        raw_name="Arsenal FC",
        external_id=57,
        team_type="Club",
        default_elo=1850
    )

    assert team is not None
    assert team.name == "Arsenal"
    assert team.elo == 1850

    # Verify ExternalTeamMapping created
    mapping = db_session.query(ExternalTeamMapping).filter_by(
        provider_name="football_data",
        external_id="57"
    ).first()
    assert mapping is not None
    assert mapping.team_id == team.id


def test_resolve_by_external_mapping(db_session):
    """Resolving a team with an existing ExternalTeamMapping returns the mapped Team immediately."""
    existing_team = Team(name="Chelsea", team_type="Club", elo=1800)
    db_session.add(existing_team)
    db_session.flush()

    mapping = ExternalTeamMapping(team_id=existing_team.id, provider_name="football_data", external_id="61")
    db_session.add(mapping)
    db_session.commit()

    resolver = TeamResolver()
    resolved = resolver.resolve(
        db=db_session,
        provider_name="football_data",
        raw_name="Chelsea FC (Different Name)",
        external_id=61
    )

    assert resolved.id == existing_team.id
    assert resolved.name == "Chelsea"


def test_resolve_by_normalized_name(db_session):
    """Resolving a team by name creates an ExternalTeamMapping link for future lookups."""
    existing_team = Team(name="South Korea", team_type="National", elo=1750)
    db_session.add(existing_team)
    db_session.commit()

    resolver = TeamResolver()
    # Alias "Korea Republic" normalizes to "South Korea"
    resolved = resolver.resolve(
        db=db_session,
        provider_name="api_football",
        raw_name="Korea Republic",
        external_id=17
    )

    assert resolved.id == existing_team.id

    # Verify ExternalTeamMapping was created
    mapping = db_session.query(ExternalTeamMapping).filter_by(
        provider_name="api_football",
        external_id="17"
    ).first()
    assert mapping is not None
    assert mapping.team_id == existing_team.id


def test_resolve_idempotency(db_session):
    """Resolving the same team multiple times returns the same entity and does not duplicate mapping rows."""
    resolver = TeamResolver()

    t1 = resolver.resolve(db_session, provider_name="thesportsdb", raw_name="Liverpool", external_id=133602)
    t2 = resolver.resolve(db_session, provider_name="thesportsdb", raw_name="Liverpool FC", external_id=133602)

    assert t1.id == t2.id

    mappings = db_session.query(ExternalTeamMapping).filter_by(
        provider_name="thesportsdb",
        external_id="133602"
    ).all()
    assert len(mappings) == 1


def test_resolve_does_not_duplicate_como_1907(db_session):
    """TheSportsDB / Football-Data short names must reuse ClubElo clubs, not mint 1500 stubs."""
    como = Team(name="Como", team_type="Club", elo=1760, elo_source="clubelo")
    db_session.add(como)
    db_session.commit()

    resolver = TeamResolver()
    resolved = resolver.resolve(
        db=db_session,
        provider_name="thesportsdb",
        raw_name="Como 1907",
        external_id=999001,
        team_type="Club",
    )

    assert resolved.id == como.id
    assert resolved.elo == 1760
    assert db_session.query(Team).filter(Team.name == "Como 1907").first() is None


def test_resolve_does_not_collapse_inter_miami_into_inter(db_session):
    inter = Team(name="Inter", team_type="Club", elo=1888, elo_source="clubelo")
    miami = Team(name="Inter Miami", team_type="Club", elo=1520, elo_source="clubelo")
    db_session.add_all([inter, miami])
    db_session.commit()

    resolver = TeamResolver()
    resolved = resolver.resolve(
        db=db_session,
        provider_name="thesportsdb",
        raw_name="Inter Miami",
        external_id=1617,
        team_type="Club",
    )
    assert resolved.id == miami.id


def test_lookup_key_matches_fc_porto(db_session):
    porto = Team(name="FC Porto", team_type="Club", elo=1805, elo_source="clubelo")
    db_session.add(porto)
    db_session.commit()

    resolver = TeamResolver()
    resolved = resolver.resolve(
        db=db_session,
        provider_name="european_draw",
        raw_name="Porto",
        team_type="Club",
        default_elo=1700,
    )
    assert resolved.id == porto.id
    assert resolved.elo == 1805
