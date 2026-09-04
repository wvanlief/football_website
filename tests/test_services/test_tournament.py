from datetime import datetime
from backend.database import Team, Fixture, Competition, Tournament, TournamentTeam
from backend.services.simulation import simulate_group_stage



def test_simulate_group_stage_finished_vs_unplayed(db_session):
    comp = Competition(name="World Cup", type="International")
    db_session.add(comp)
    db_session.flush()
    tourney = Tournament(competition_id=comp.id, season_name="2026")
    db_session.add(tourney)
    db_session.flush()

    # Setup teams
    t1 = Team(name="Germany", elo=1900)
    t2 = Team(name="Scotland", elo=1650)
    db_session.add_all([t1, t2])
    db_session.flush()

    tt1 = TournamentTeam(tournament_id=tourney.id, team_id=t1.id, group_name="A")
    tt2 = TournamentTeam(tournament_id=tourney.id, team_id=t2.id, group_name="A")
    db_session.add_all([tt1, tt2])
    db_session.flush()
    
    # One finished match
    f1 = Fixture(
        tournament_id=tourney.id,
        home_team_id=t1.id,
        away_team_id=t2.id,
        stage="Group Stage",
        status="Finished",
        home_score=2,
        away_score=1,
        date_utc=datetime.fromisoformat("2026-06-11T20:00:00")
    )
    # One scheduled match (needs simulation)
    f2 = Fixture(
        tournament_id=tourney.id,
        home_team_id=t2.id,
        away_team_id=t1.id,
        stage="Group Stage",
        status="Scheduled",
        date_utc=datetime.fromisoformat("2026-06-12T20:00:00")
    )
    db_session.add_all([f1, f2])
    db_session.commit()
    
    groups_data = simulate_group_stage(db_session)
    
    assert "A" in groups_data
    germany_stats = next(s for s in groups_data["A"] if s["name"] == "Germany")
    scotland_stats = next(s for s in groups_data["A"] if s["name"] == "Scotland")
    assert germany_stats["played"] == 2
    assert scotland_stats["played"] == 2



def test_get_all_third_placed_teams(db_session):
    from backend.services.tournament import get_all_third_placed_teams
    comp = Competition(name="World Cup 3", type="International")
    db_session.add(comp)
    db_session.flush()
    tourney = Tournament(competition_id=comp.id, season_name="2026")
    db_session.add(tourney)
    db_session.flush()
    
    groups = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L"]
    for idx, g in enumerate(groups):
        for j in range(3):
            t = Team(name=f"Team_{g}_{j}", elo=1500 + idx*10 + j)
            db_session.add(t)
            db_session.flush()
            tt = TournamentTeam(tournament_id=tourney.id, team_id=t.id, group_name=g)
            db_session.add(tt)
            db_session.flush()
            
    db_session.commit()
    
    thirds = get_all_third_placed_teams(db_session)
    assert len(thirds) == 12
    assert thirds[0]["group"] == "L"


def test_resolve_placeholder_name(db_session):
    from backend.services.tournament import resolve_placeholder_name
    
    comp = Competition(name="World Cup Placeholder Test", type="International")
    db_session.add(comp)
    db_session.flush()
    tourney = Tournament(competition_id=comp.id, season_name="2026")
    db_session.add(tourney)
    db_session.flush()
    
    # 1. Setup teams
    t1 = Team(name="Spain", elo=2000)
    t2 = Team(name="Germany", elo=1900)
    db_session.add_all([t1, t2])
    db_session.flush()
    
    # 2. Add referenced fixture with resolved teams
    f_ref = Fixture(
        tournament_id=tourney.id,
        home_team_id=t1.id,
        away_team_id=t2.id,
        stage="Round of 32",
        status="Scheduled",
        api_id="78",
        date_utc=datetime.now()
    )
    db_session.add(f_ref)
    
    # 3. Add referenced fixture with placeholder/unresolved teams
    f_ref_unresolved = Fixture(
        tournament_id=tourney.id,
        home_team_id=None,
        away_team_id=None,
        home_team_placeholder="Winner Group A",
        away_team_placeholder="Runner-up Group B",
        stage="Round of 32",
        status="Scheduled",
        api_id="80",
        date_utc=datetime.now()
    )
    db_session.add(f_ref_unresolved)
    db_session.commit()
    
    # Test case 1: Referenced match has resolved teams
    res1 = resolve_placeholder_name(db_session, "Winner Match 78", tourney.id)
    assert res1 == "Winner Match 78 (Spain or Germany)"
    
    # Test case 2: Referenced match has unresolved placeholder teams (simplified)
    res2 = resolve_placeholder_name(db_session, "Winner Match 80", tourney.id)
    assert res2 == "Winner Match 80 (Winner A or Runner-up B)"
    
    # Test case 3: Referenced match does not exist
    res3 = resolve_placeholder_name(db_session, "Winner Match 999", tourney.id)
    assert res3 == "Winner Match 999"
    
    # Test case 4: Normal group placeholder (does not reference a match)
    res4 = resolve_placeholder_name(db_session, "Winner Group A", tourney.id)
    assert res4 == "Winner Group A"


def test_propagate_knockout_fixtures(db_session):
    from backend.services.tournament import propagate_knockout_fixtures
    
    comp = Competition(name="World Cup Knockout Propagation Test", type="International")
    db_session.add(comp)
    db_session.flush()
    tourney = Tournament(competition_id=comp.id, season_name="2026")
    db_session.add(tourney)
    db_session.flush()
    
    # 1. Setup teams
    t1 = Team(name="France", elo=1950)
    t2 = Team(name="Belgium", elo=1850)
    db_session.add_all([t1, t2])
    db_session.flush()
    
    # 2. Add finished knockout fixture (api_id="73", stage="Round of 32")
    # Winner: France (t1.id)
    f_finished = Fixture(
        tournament_id=tourney.id,
        home_team_id=t1.id,
        away_team_id=t2.id,
        stage="Round of 32",
        status="Finished",
        api_id="73",
        home_score=2,
        away_score=1,
        winner_id=t1.id,
        date_utc=datetime.now()
    )
    db_session.add(f_finished)
    
    # 3. Add next knockout fixture (api_id="90", stage="Round of 16")
    # This should be populated by winner of match 73 (France) as "home" team according to NEXT_ROUND_LOOKUP
    f_next = Fixture(
        tournament_id=tourney.id,
        home_team_id=None,
        away_team_id=None,
        home_team_placeholder="Winner Match 73",
        away_team_placeholder="Winner Match 75",
        stage="Round of 16",
        status="Scheduled",
        api_id="90",
        date_utc=datetime.now()
    )
    db_session.add(f_next)
    
    # 4. Add third-place play-off (api_id="103")
    t3 = Team(name="Italy", elo=1880)
    t4 = Team(name="Portugal", elo=1900)
    db_session.add_all([t3, t4])
    db_session.flush()
    
    f_semi = Fixture(
        tournament_id=tourney.id,
        home_team_id=t3.id,
        away_team_id=t4.id,
        stage="Semi-final",
        status="Finished",
        api_id="101",
        home_score=0,
        away_score=1,
        winner_id=t4.id, # Portugal wins, Italy loses
        date_utc=datetime.now()
    )
    db_session.add(f_semi)
    
    f_third = Fixture(
        tournament_id=tourney.id,
        home_team_id=None,
        away_team_id=None,
        home_team_placeholder="Loser Match 101",
        away_team_placeholder="Loser Match 102",
        stage="Third-place play-off",
        status="Scheduled",
        api_id="103",
        date_utc=datetime.now()
    )
    db_session.add(f_third)
    
    db_session.commit()
    
    # Run propagation
    propagate_knockout_fixtures(db_session)
    db_session.commit()
    
    # Asserts
    db_session.refresh(f_next)
    db_session.refresh(f_third)
    
    # Match 73 winner (France) propagated to Match 90 home
    assert f_next.home_team_id == t1.id
    assert f_next.home_team_placeholder is None
    
    # Match 101 loser (Italy) propagated to Match 103 home
    assert f_third.home_team_id == t3.id
    assert f_third.home_team_placeholder is None


def test_world_cup_fallback_is_scoped_to_tournament(db_session):
    from backend.services.tournament import propagate_knockout_fixtures

    comp = Competition(name="FIFA World Cup", type="International")
    db_session.add(comp)
    db_session.flush()
    source_tourney = Tournament(competition_id=comp.id, season_name="2026")
    other_tourney = Tournament(competition_id=comp.id, season_name="2030")
    winner = Team(name="Scoped Winner", elo=1900)
    loser = Team(name="Scoped Loser", elo=1800)
    db_session.add_all([source_tourney, other_tourney, winner, loser])
    db_session.flush()
    source = Fixture(
        tournament_id=source_tourney.id,
        home_team_id=winner.id,
        away_team_id=loser.id,
        stage="Round of 32",
        status="Finished",
        api_id="73",
        home_score=1,
        away_score=0,
        winner_id=winner.id,
        date_utc=datetime.now(),
    )
    correct_target = Fixture(
        tournament_id=source_tourney.id,
        stage="Round of 16",
        status="Scheduled",
        api_id="90",
        date_utc=datetime.now(),
    )
    other_target = Fixture(
        tournament_id=other_tourney.id,
        stage="Round of 16",
        status="Scheduled",
        api_id="90",
        date_utc=datetime.now(),
    )
    db_session.add_all([source, correct_target, other_target])
    db_session.commit()

    propagate_knockout_fixtures(db_session)
    db_session.commit()

    assert correct_target.home_team_id == winner.id
    assert other_target.home_team_id is None


def test_numeric_fallback_is_disabled_for_non_world_cup(db_session):
    from backend.services.tournament import propagate_knockout_fixtures

    comp = Competition(name="Domestic Cup", type="Cup")
    db_session.add(comp)
    db_session.flush()
    tourney = Tournament(competition_id=comp.id, season_name="2026")
    winner = Team(name="Domestic Winner", elo=1900)
    loser = Team(name="Domestic Loser", elo=1800)
    db_session.add_all([tourney, winner, loser])
    db_session.flush()
    source = Fixture(
        tournament_id=tourney.id,
        home_team_id=winner.id,
        away_team_id=loser.id,
        stage="Round of 32",
        status="Finished",
        api_id="73",
        home_score=1,
        away_score=0,
        winner_id=winner.id,
        date_utc=datetime.now(),
    )
    target = Fixture(
        tournament_id=tourney.id,
        stage="Round of 16",
        status="Scheduled",
        api_id="90",
        date_utc=datetime.now(),
    )
    db_session.add_all([source, target])
    db_session.commit()

    propagate_knockout_fixtures(db_session)
    db_session.commit()

    assert target.home_team_id is None


def test_db_driven_propagation(db_session):
    from backend.database import Competition, Tournament, Team, Fixture, FixtureDependency
    from backend.services.tournament import propagate_knockout_fixtures
    
    comp = Competition(name="DB Dependency Test", type="Cup", format_engine="league_phase_knockout")
    db_session.add(comp)
    db_session.flush()
    tourney = Tournament(competition_id=comp.id, season_name="2025/26", status="Active")
    db_session.add(tourney)
    db_session.flush()
    
    t_home = Team(name="Real Madrid Test", elo=1900)
    t_away = Team(name="Man City Test", elo=1950)
    db_session.add_all([t_home, t_away])
    db_session.flush()
    
    f_source = Fixture(
        tournament_id=tourney.id,
        home_team_id=t_home.id,
        away_team_id=t_away.id,
        stage="Knockout Play-off",
        status="Finished",
        home_score=2,
        away_score=0,
        winner_id=t_home.id,
        date_utc=datetime.now()
    )
    f_target = Fixture(
        tournament_id=tourney.id,
        home_team_id=None,
        away_team_id=None,
        home_team_placeholder="Winner Play-off",
        stage="Round of 16",
        status="Scheduled",
        date_utc=datetime.now()
    )
    db_session.add_all([f_source, f_target])
    db_session.flush()
    
    dep = FixtureDependency(
        source_fixture_id=f_source.id,
        target_fixture_id=f_target.id,
        slot="home",
        result_type="winner"
    )
    db_session.add(dep)
    db_session.commit()
    
    propagate_knockout_fixtures(db_session)
    db_session.commit()
    db_session.refresh(f_target)
    
    assert f_target.home_team_id == t_home.id
    assert f_target.home_team_placeholder is None

def test_get_grouped_fixtures_offseason_empty_today_tomorrow(db_session):
    from datetime import timedelta, timezone
    from backend.services.tournament import get_grouped_fixtures

    comp = Competition(name="Future Cup", type="International")
    db_session.add(comp)
    db_session.flush()
    tourney = Tournament(competition_id=comp.id, season_name="2026", status="Active")
    db_session.add(tourney)
    db_session.flush()

    t1 = Team(name="Team A", elo=1500)
    t2 = Team(name="Team B", elo=1500)
    db_session.add_all([t1, t2])
    db_session.flush()

    # Fixture 60 days in the future
    future_date = datetime.now(timezone.utc) + timedelta(days=60)
    f = Fixture(
        tournament_id=tourney.id,
        home_team_id=t1.id,
        away_team_id=t2.id,
        stage="Group Stage",
        status="Scheduled",
        date_utc=future_date
    )
    db_session.add(f)
    db_session.commit()

    grouped = get_grouped_fixtures(db_session, "UTC", tournament_id=tourney.id)
    assert grouped["is_offseason"] is True
    assert len(grouped["today"]) == 0
    assert len(grouped["tomorrow"]) == 0
    assert len(grouped["this_week"]) >= 1
    assert grouped["offseason_notice"] is not None


def test_upcoming_gems_watchability_filter(db_session):
    from datetime import timedelta, timezone
    from backend.services.tournament import get_grouped_fixtures

    comp = Competition(name="Gems League", type="League", format_engine="league")
    db_session.add(comp)
    db_session.flush()
    tourney = Tournament(competition_id=comp.id, season_name="2026/27", status="Active")
    db_session.add(tourney)
    db_session.flush()

    teams = [Team(name=f"Team {i}", elo=1500 + i * 50) for i in range(8)]
    db_session.add_all(teams)
    db_session.flush()

    # 4 upcoming matches in 3 days
    match_date = datetime.now(timezone.utc) + timedelta(days=3)
    
    # 3 High quality gems + 1 low quality match
    scores = [88.0, 79.0, 72.0, 45.0]
    for idx, score in enumerate(scores):
        f = Fixture(
            tournament_id=tourney.id,
            home_team_id=teams[idx * 2].id,
            away_team_id=teams[idx * 2 + 1].id,
            stage="Regular Season",
            status="Scheduled",
            date_utc=match_date + timedelta(hours=idx),
            watchability_score=score
        )
        db_session.add(f)
    db_session.commit()

    grouped = get_grouped_fixtures(db_session, "UTC", tournament_id=tourney.id)
    gems = grouped["this_week"]
    
    # Assert low score (45.0) was filtered out and gems are sorted descending
    assert len(gems) == 3
    assert gems[0]["watchability"]["overall"] == 88.0
    assert gems[1]["watchability"]["overall"] == 79.0
    assert gems[2]["watchability"]["overall"] == 72.0



