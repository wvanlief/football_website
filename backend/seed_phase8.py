"""
Seeder script for Phase 8: Domestic Cups & Nations League
Seeds sample Copa del Rey two-legged ties and UEFA Nations League division structures.
"""
from datetime import datetime, timedelta, timezone
from backend.database import SessionLocal, Competition, Tournament, Team, TournamentTeam, Fixture, FixtureDependency
from backend.services.tournament import propagate_knockout_fixtures, evaluate_nations_league_promotions

def seed_phase8_data():
    db = SessionLocal()
    try:
        print("--- Seeding Phase 8 Data ---")
        
        # 1. Copa del Rey (Two-legged Cup)
        copa_comp = db.query(Competition).filter(Competition.name == "Copa del Rey").first()
        if not copa_comp:
            copa_comp = Competition(
                name="Copa del Rey",
                type="Cup",
                format_engine="cup",
                badge="🏆",
                home_advantage_elo=30
            )
            db.add(copa_comp)
            db.flush()
            
        copa_tourney = db.query(Tournament).filter(Tournament.competition_id == copa_comp.id, Tournament.season_name == "2025/26").first()
        if not copa_tourney:
            copa_tourney = Tournament(
                competition_id=copa_comp.id,
                season_name="2025/26",
                status="Active"
            )
            db.add(copa_tourney)
            db.flush()
            
            # Helper team fetcher/creator
            def get_or_create_team(name, elo):
                t = db.query(Team).filter(Team.name == name).first()
                if not t:
                    t = Team(name=name, elo=elo)
                    db.add(t)
                    db.flush()
                return t
                
            rm = get_or_create_team("Real Madrid", 1950)
            barca = get_or_create_team("Barcelona", 1930)
            atletico = get_or_create_team("Atletico Madrid", 1880)
            athletic = get_or_create_team("Athletic Club", 1840)
            
            for team in [rm, barca, atletico, athletic]:
                tt = db.query(TournamentTeam).filter(TournamentTeam.tournament_id == copa_tourney.id, TournamentTeam.team_id == team.id).first()
                if not tt:
                    db.add(TournamentTeam(tournament_id=copa_tourney.id, team_id=team.id))
            db.flush()
            
            # SF 1: Leg 1 (Barca vs Real Madrid)
            sf1_l1 = Fixture(
                tournament_id=copa_tourney.id,
                home_team_id=barca.id,
                away_team_id=rm.id,
                stage="Semi-final",
                status="Finished",
                home_score=2,
                away_score=1,
                leg_number=1,
                date_utc=datetime.now(timezone.utc) - timedelta(days=14)
            )
            # SF 1: Leg 2 (Real Madrid vs Barca)
            sf1_l2 = Fixture(
                tournament_id=copa_tourney.id,
                home_team_id=rm.id,
                away_team_id=barca.id,
                stage="Semi-final",
                status="Finished",
                home_score=3,
                away_score=1,
                leg_number=2,
                date_utc=datetime.now(timezone.utc) - timedelta(days=7)
            )
            
            # SF 2: Leg 1 (Athletic vs Atletico)
            sf2_l1 = Fixture(
                tournament_id=copa_tourney.id,
                home_team_id=athletic.id,
                away_team_id=atletico.id,
                stage="Semi-final",
                status="Finished",
                home_score=1,
                away_score=0,
                leg_number=1,
                date_utc=datetime.now(timezone.utc) - timedelta(days=14)
            )
            # SF 2: Leg 2 (Atletico vs Athletic)
            sf2_l2 = Fixture(
                tournament_id=copa_tourney.id,
                home_team_id=atletico.id,
                away_team_id=athletic.id,
                stage="Semi-final",
                status="Finished",
                home_score=2,
                away_score=0,
                leg_number=2,
                date_utc=datetime.now(timezone.utc) - timedelta(days=7)
            )
            
            # Final Placeholder
            final_fix = Fixture(
                tournament_id=copa_tourney.id,
                home_team_placeholder="Winner SF 1",
                away_team_placeholder="Winner SF 2",
                stage="Final",
                status="Scheduled",
                leg_number=1,
                date_utc=datetime.now(timezone.utc) + timedelta(days=30)
            )
            db.add_all([sf1_l1, sf1_l2, sf2_l1, sf2_l2, final_fix])
            db.flush()
            
            # Dependencies
            db.add(FixtureDependency(source_fixture_id=sf1_l2.id, target_fixture_id=final_fix.id, slot="home", result_type="winner"))
            db.add(FixtureDependency(source_fixture_id=sf2_l2.id, target_fixture_id=final_fix.id, slot="away", result_type="winner"))
            db.commit()
            
            propagate_knockout_fixtures(db)
            db.commit()
            print("Copa del Rey seeded and propagated.")
        else:
            print("Copa del Rey already exists.")
            
        # 2. UEFA Nations League
        nl_comp = db.query(Competition).filter(Competition.name == "UEFA Nations League").first()
        if not nl_comp:
            nl_comp = Competition(
                name="UEFA Nations League",
                type="International",
                format_engine="nations_league",
                badge="🇪🇺"
            )
            db.add(nl_comp)
            db.flush()
            
        nl_tourney = db.query(Tournament).filter(Tournament.competition_id == nl_comp.id, Tournament.season_name == "2026/27").first()
        if not nl_tourney:
            nl_tourney = Tournament(
                competition_id=nl_comp.id,
                season_name="2026/27",
                status="Active"
            )
            db.add(nl_tourney)
            db.flush()
            
            def get_or_create_nat_team(name, elo):
                t = db.query(Team).filter(Team.name == name).first()
                if not t:
                    t = Team(name=name, elo=elo)
                    db.add(t)
                    db.flush()
                return t
                
            # League A Group 1
            a1_teams = [
                ("Spain", 2165), ("France", 2082), ("Italy", 1950), ("Belgium", 1920)
            ]
            # League B Group 1
            b1_teams = [
                ("England", 2020), ("Greece", 1750), ("Ireland", 1680), ("Finland", 1620)
            ]
            
            for name, elo in a1_teams:
                t = get_or_create_nat_team(name, elo)
                db.add(TournamentTeam(tournament_id=nl_tourney.id, team_id=t.id, division="A", group_name="1"))
                
            for name, elo in b1_teams:
                t = get_or_create_nat_team(name, elo)
                db.add(TournamentTeam(tournament_id=nl_tourney.id, team_id=t.id, division="B", group_name="1"))
            db.commit()
            
            evaluate_nations_league_promotions(db, nl_tourney.id)
            db.commit()
            print("UEFA Nations League seeded.")
        else:
            print("UEFA Nations League already exists.")
            
        print("--- Phase 8 Seeding Complete ---")
    finally:
        db.close()

if __name__ == "__main__":
    seed_phase8_data()
