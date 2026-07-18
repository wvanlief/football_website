# findfootball.games 🏆 - World Cup Watchability Index

findfootball.games is a dynamic web application that rates and ranks upcoming football matches to help fans prioritize which games to watch. Built for the expanded 48-team 2026 World Cup format, the app computes a **Watchability Score** for each fixture using a customizable mathematical formula. It also includes a **Knockout Bracket Predictor** that dynamically simulates the tournament path based on ELO and match results.

---

## ✨ Features

### 1. Dynamic Watchability Engine
- **Customizable Weights**: Slide out the **Engine Weights** panel to adjust:
  - **ELO Proximity** (Favors closely-matched teams)
  - **Betting Odds Competitiveness** (Favors tight, unpredictable outcomes)
  - **Player & Team Form** (Highlights hot scoring streaks)
  - **Match Stage & Stakes** (Boosts knockout games and high-stakes matches)
- **Real-Time Recalculation**: The backend automatically normalizes the weights and updates match ratings on-the-fly.

### 2. The Hot List
- A dedicated, high-priority feed showing only fixtures with a **Watchability Score of 75% or higher**.

### 3. Country Profiles
- Displays each country's current ELO rating, group standing, spotlight players, and form indicator (`W`/`D`/`L`) derived from active matches and historical form padding.
- Lists all future fixtures scheduled for that country.

### 4. Group Standings & Standings Solver
- Glassmorphic group tables detailing PTS, GD, GF, GA, and qualification zone borders.
- Integrates a **chronological fixture listing** alongside a **Watchability Leaderboard** view.

### 5. Tournament Knockout Bracket Predictor
- Dynamic simulations from the **Round of 32** to the **Finals**.
- Implements a **bipartite constraint backtracking solver** to assign the 8 best 3rd-placed teams into their correct knockout slots based on FIFA regulations.
- Re-simulates automatically when team weights are adjusted or group matches are updated.

---

## 🎨 Design Themes
findfootball.games features five rich, responsive themes synced globally across all pages:
- 🌌 **Midnight Neon** (Default dark/neon vibe)
- 🏛️ **Roman Empire** (Imperial red and gold)
- 🍃 **Clubhouse Sage** (Soft green and off-white pitch styling)
- ⚽ **Tactical Pitch** (Dark green tactical layout)
- 🚩 **Big Flag** (Translucent cards overlaying large background team flags)

---

## 🛠️ Technology Stack
- **Backend**: Python 3, FastAPI, SQLite, SQLAlchemy, Uvicorn, Pydantic
- **Frontend**: HTML5, Vanilla CSS3 (Custom Grid & Flexbox properties), Vanilla JS (ES6)
- **Asset Integrations**: FontAwesome, Google Fonts, Flag CDN

---

## 🚀 Getting Started

### 1. Prerequisites
Make sure you have Python 3.10+ installed.

### 2. Installation
Clone the repository and install the dependencies:
```bash
pip install -r requirements.txt
```

### 3. Running the Server
Launch the development server by executing `run.py`:
```bash
python run.py
```
Open your browser and navigate to **`http://localhost:8000`** to access the application.

---

## 💾 Database Migrations & Seeding

The database layer utilizes SQLAlchemy and is compatible with both SQLite (local development) and PostgreSQL (production).

### 1. Migrations (Alembic)
Apply the latest database migrations before running the application:
```bash
python -m alembic upgrade head
```

### 2. Seeding Local SQLite DB
Populate your local SQLite database with initial tournaments, clubs, and schedules:
```bash
# 1. Fetch clubs and roster spotlights (Premier League 2026/27)
python -m backend.ingestor fetch-teams --league=39 --season=2026

# 2. Apply verified ELO ratings
python -m backend.ingestor apply-elo-matches --file=backend/data/elo_name_review.json

# 3. Seed Premier League fixture schedules (2025/26 and 2026/27)
python -m backend.ingestor seed-competition --league=39 --season=2025 --comp-name="Premier League" --comp-type="League" --format-engine="league"
python -m backend.ingestor seed-competition --league=39 --season=2026 --comp-name="Premier League" --comp-type="League" --format-engine="league"
```

### 3. Seeding Remote Database (e.g. Railway PostgreSQL)
To seed a remote database, configure `DATABASE_URL` in your `.env` file (e.g., `DATABASE_URL=postgresql://user:pass@host:port/dbname`) and execute the same seeder commands locally. The Python scripts will load the connection string from `.env` and apply all migrations and seed data directly to the remote instance.

