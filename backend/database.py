import os
from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./football_games.db")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Team(Base):
    __tablename__ = "teams"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    group_name = Column(String, nullable=True) # A, B, C, etc.
    elo = Column(Integer, default=1500)
    form_score = Column(Float, default=50.0) # 0 to 100
    win_streak = Column(Integer, default=0)
    draw_streak = Column(Integer, default=0)
    loss_streak = Column(Integer, default=0)

class Player(Base):
    __tablename__ = "players"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    team_name = Column(String, nullable=False)
    position = Column(String, nullable=True) # Forward, Midfielder, Defender, Goalkeeper
    form_score = Column(Float, default=50.0) # 0 to 100

class Fixture(Base):
    __tablename__ = "fixtures"
    
    id = Column(Integer, primary_key=True, index=True)
    home_team_name = Column(String, nullable=False)
    away_team_name = Column(String, nullable=False)
    date = Column(String, nullable=False) # ISO format, e.g., "2026-06-03T20:00:00"
    stage = Column(String, nullable=False) # Group stage, Round of 16, Quarter-final, Semi-final, Final
    status = Column(String, default="Scheduled") # Scheduled, Live, Finished
    home_score = Column(Integer, nullable=True)
    away_score = Column(Integer, nullable=True)
    
    # Odds
    odds_home = Column(Float, default=2.0)
    odds_draw = Column(Float, default=3.0)
    odds_away = Column(Float, default=2.0)
    
    # Watchability & Components
    watchability_score = Column(Float, default=0.0)
    competitiveness_score = Column(Float, default=0.0)
    odds_score = Column(Float, default=0.0)
    form_score = Column(Float, default=0.0)
    narrative_score = Column(Float, default=0.0)
    reasons_json = Column(String, default="[]") # JSON list of narrative explanations

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
