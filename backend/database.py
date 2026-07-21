import os
from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, DateTime, Boolean, UniqueConstraint
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

DATABASE_URL = os.getenv("DATABASE_PUBLIC_URL") or os.getenv("DATABASE_URL", "sqlite:///./football_games.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Competition(Base):
    __tablename__ = "competitions"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    type = Column(String, nullable=False) # League, Cup, International
    format_engine = Column(String, default="group_knockout")  # "league" | "cup" | "group_knockout" | "league_phase_knockout" | "nations_league"
    odds_api_sport_key = Column(String, nullable=True)        # e.g. "soccer_epl"
    home_advantage_elo = Column(Integer, default=0)           # e.g. +70 for leagues, 0 for WC
    neutral_venue = Column(Boolean, default=False)            # default status for home advantage calculations
    relegation_spots = Column(Integer, default=0)
    promotion_spots = Column(Integer, default=0)
    relegation_playoff_spots = Column(Integer, default=0)
    api_league_id = Column(Integer, nullable=True)
    badge = Column(String, nullable=True, default="⚽")
    
    tournaments = relationship("Tournament", back_populates="competition", cascade="all, delete-orphan")


class Tournament(Base):
    __tablename__ = "tournaments"
    
    id = Column(Integer, primary_key=True, index=True)
    competition_id = Column(Integer, ForeignKey("competitions.id", ondelete="CASCADE"), nullable=False, index=True)
    season_name = Column(String, nullable=False) # e.g. 2026
    status = Column(String, default="Active") # Active, Completed
    
    competition = relationship("Competition", back_populates="tournaments")
    fixtures = relationship("Fixture", back_populates="tournament", cascade="all, delete-orphan")
    tournament_teams = relationship("TournamentTeam", back_populates="tournament", cascade="all, delete-orphan")

class Team(Base):
    __tablename__ = "teams"
    
    __table_args__ = (
        UniqueConstraint("name", "country_code", name="uq_team_name_country"),
    )
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    country_code = Column(String, nullable=True)
    team_type = Column(String, default="National")    # "National" | "Club"
    elo_source = Column(String, default="eloratings") # "eloratings" | "clubelo" | "manual"
    api_id = Column(Integer, nullable=True, unique=True, index=True) # API-Football team ID
    
    # ELO & Form cache (stored on team for fast lookup)
    elo = Column(Integer, default=1500)
    form_score = Column(Float, default=50.0) # 0 to 100
    win_streak = Column(Integer, default=0)
    draw_streak = Column(Integer, default=0)
    loss_streak = Column(Integer, default=0)

    contracts = relationship("PlayerContract", back_populates="team", cascade="all, delete-orphan")
    tournament_teams = relationship("TournamentTeam", back_populates="team", cascade="all, delete-orphan")
    elo_history = relationship("EloHistory", back_populates="team", cascade="all, delete-orphan")

class TournamentTeam(Base):
    __tablename__ = "tournament_teams"
    
    tournament_id = Column(Integer, ForeignKey("tournaments.id", ondelete="CASCADE"), primary_key=True, index=True)
    team_id = Column(Integer, ForeignKey("teams.id", ondelete="CASCADE"), primary_key=True, index=True)
    group_name = Column(String, nullable=True) # A, B, C, etc.
    tournament_status = Column(String, default="Active") # Active, Eliminated, Champion
    final_stage_reached = Column(String, nullable=True) # Group Stage, Round of 16, etc.
    division = Column(String, nullable=True)          # e.g. "A", "B", "C", "D"
    promoted = Column(Boolean, default=False)
    relegated = Column(Boolean, default=False)
    
    # Standings Cache
    points = Column(Integer, default=0)
    wins = Column(Integer, default=0)
    draws = Column(Integer, default=0)
    losses = Column(Integer, default=0)
    goals_for = Column(Integer, default=0)
    goals_against = Column(Integer, default=0)
    
    tournament = relationship("Tournament", back_populates="tournament_teams")
    team = relationship("Team", back_populates="tournament_teams")

class Player(Base):
    __tablename__ = "players"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    position = Column(String, nullable=True) # Forward, Midfielder, Defender, Goalkeeper
    form_score = Column(Float, default=50.0)
    
    contracts = relationship("PlayerContract", back_populates="player", cascade="all, delete-orphan")
    match_stats = relationship("PlayerMatchStat", back_populates="player", cascade="all, delete-orphan")

class PlayerContract(Base):
    __tablename__ = "player_contracts"
    
    id = Column(Integer, primary_key=True, index=True)
    player_id = Column(Integer, ForeignKey("players.id", ondelete="CASCADE"), nullable=False, index=True)
    team_id = Column(Integer, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True)
    type = Column(String, default="Country") # Club, Country
    is_active = Column(Boolean, default=True)
    
    player = relationship("Player", back_populates="contracts")
    team = relationship("Team", back_populates="contracts")

class Fixture(Base):
    __tablename__ = "fixtures"
    
    __table_args__ = (
        UniqueConstraint("tournament_id", "api_id", name="uq_fixture_tournament_api"),
    )
    
    id = Column(Integer, primary_key=True, index=True)
    tournament_id = Column(Integer, ForeignKey("tournaments.id", ondelete="CASCADE"), nullable=False, index=True)
    home_team_id = Column(Integer, ForeignKey("teams.id", ondelete="CASCADE"), nullable=True, index=True)
    away_team_id = Column(Integer, ForeignKey("teams.id", ondelete="CASCADE"), nullable=True, index=True)
    date_utc = Column(DateTime, nullable=False, index=True)
    stage = Column(String, nullable=False) # Group Stage, Round of 16, etc.
    status = Column(String, default="Scheduled") # Scheduled, Live, Finished
    home_score = Column(Integer, nullable=True)
    away_score = Column(Integer, nullable=True)
    matchday_number = Column(Integer, nullable=True)  # Game Week number
    
    # Placeholders & External ID mapping
    home_team_placeholder = Column(String, nullable=True)
    away_team_placeholder = Column(String, nullable=True)
    api_id = Column(String, nullable=True, index=True)

    # Knockout extension fields
    home_penalty_score = Column(Integer, nullable=True)
    away_penalty_score = Column(Integer, nullable=True)
    has_extra_time = Column(Boolean, default=False)
    has_penalties = Column(Boolean, default=False)
    leg_number = Column(Integer, default=1)
    winner_id = Column(Integer, ForeignKey("teams.id", ondelete="SET NULL"), nullable=True)
    
    # Watchability Cache
    watchability_score = Column(Float, default=0.0)
    competitiveness_score = Column(Float, default=0.0)
    odds_score = Column(Float, default=0.0)
    form_score = Column(Float, default=0.0)
    narrative_score = Column(Float, default=0.0)
    reasons_json = Column(String, default="[]") # JSON list of narrative explanations
    
    tournament = relationship("Tournament", back_populates="fixtures")
    home_team = relationship("Team", foreign_keys=[home_team_id])
    away_team = relationship("Team", foreign_keys=[away_team_id])
    winner_team = relationship("Team", foreign_keys=[winner_id])
    
    odds_history = relationship("FixtureOdds", back_populates="fixture", cascade="all, delete-orphan")
    player_stats = relationship("PlayerMatchStat", back_populates="fixture", cascade="all, delete-orphan")

    @property
    def latest_odds(self):
        if self.odds_history:
            return sorted(self.odds_history, key=lambda o: o.id, reverse=True)[0]
        # Return a fallback object with default odds so code doesn't crash if no odds are seeded
        class FallbackOdds:
            odds_home = 2.0
            odds_draw = 3.0
            odds_away = 2.0
        return FallbackOdds()

class FixtureOdds(Base):
    __tablename__ = "fixture_odds"
    
    id = Column(Integer, primary_key=True, index=True)
    fixture_id = Column(Integer, ForeignKey("fixtures.id", ondelete="CASCADE"), nullable=False, index=True)
    recorded_at = Column(DateTime, nullable=False, index=True)
    odds_home = Column(Float, nullable=False)
    odds_draw = Column(Float, nullable=False)
    odds_away = Column(Float, nullable=False)
    
    fixture = relationship("Fixture", back_populates="odds_history")

class PlayerMatchStat(Base):
    __tablename__ = "player_match_stats"
    
    id = Column(Integer, primary_key=True, index=True)
    fixture_id = Column(Integer, ForeignKey("fixtures.id", ondelete="CASCADE"), nullable=False, index=True)
    player_id = Column(Integer, ForeignKey("players.id", ondelete="CASCADE"), nullable=False, index=True)
    rating_score = Column(Float, default=0.0)
    
    # Specific player metrics
    goals = Column(Integer, default=0)
    assists = Column(Integer, default=0)
    minutes_played = Column(Integer, default=0)
    passes_completed = Column(Integer, default=0)
    tackles_made = Column(Integer, default=0)
    yellow_cards = Column(Integer, default=0)
    red_cards = Column(Integer, default=0)
    
    # Extensible metrics JSON field
    stats_json = Column(String, nullable=True) # for saves, fouls, clean sheets, etc.
    
    fixture = relationship("Fixture", back_populates="player_stats")
    player = relationship("Player", back_populates="match_stats")

class EloHistory(Base):
    __tablename__ = "elo_history"
    
    id = Column(Integer, primary_key=True, index=True)
    team_id = Column(Integer, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True)
    recorded_at = Column(DateTime, nullable=False, index=True)
    elo_rating = Column(Integer, nullable=False)
    
    team = relationship("Team", back_populates="elo_history")

class FixtureDependency(Base):
    __tablename__ = "fixture_dependencies"
    
    id = Column(Integer, primary_key=True)
    source_fixture_id = Column(Integer, ForeignKey("fixtures.id", ondelete="CASCADE"), index=True)
    target_fixture_id = Column(Integer, ForeignKey("fixtures.id", ondelete="CASCADE"), index=True)
    slot = Column(String)         # "home" | "away"
    result_type = Column(String)  # "winner" | "loser"

def init_db():
    # Schema changes are managed via Alembic migrations.
    # We still run create_all to ensure simple initializations (e.g. in tests) succeed.
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
