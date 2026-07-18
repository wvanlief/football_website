# Football Website — Expansion Wiki & Reference Guide

This wiki serves as a permanent reference point for the multi-tournament architecture and database schema design. It is updated at the completion of each implementation phase.

---

## 1. Database Schema & Architecture

The database is built on a relational SQLite model managed via SQLAlchemy, with migrations handled by Alembic. 

### 1.1 Core Models & Expansion Columns
Below are the schema updates implemented in **Phase 1: Foundation & Schema**:

#### `competitions` (Competition)
Stores the unique competition definition (persisting across seasons).
* `format_engine` (String, default: `"group_knockout"`): Defines the structural tournament engine. Allowed values: `"league"`, `"cup"`, `"group_knockout"`, `"league_phase_knockout"`, `"nations_league"`.
* `odds_api_sport_key` (String, Nullable): Maps the competition to The Odds API key (e.g. `"soccer_epl"`).
* `home_advantage_elo` (Integer, default: `0`): Configurable ELO rating boost applied to home teams (replaces legacy hardcoded `+100` ELO logic).
* `neutral_venue` (Boolean, default: `False`): Denotes whether matches in this competition are played on neutral grounds.
* `relegation_spots` (Integer, default: `0`): Number of direct relegation places.
* `promotion_spots` (Integer, default: `0`): Number of direct promotion places.
* `relegation_playoff_spots` (Integer, default: `0`): Number of promotion/relegation playoff places.

#### `teams` (Team)
Stores all team details (both club and national teams).
* `team_type` (String, default: `"National"`): Differentiates between club and national teams. Allowed values: `"Club"`, `"National"`.
* `elo_source` (String, default: `"eloratings"`): Source registry for ELO sync. Allowed values: `"clubelo"`, `"eloratings"`, `"manual"`.
* `api_id` (Integer, unique, Nullable): API-Football team ID mapping.
* **Uniqueness**: The global unique constraint on `Team.name` is replaced with a composite unique constraint `uq_team_name_country` on `(name, country_code)` to allow name reuse across different countries/contexts.

#### `fixtures` (Fixture)
Stores match schedules, scores, and cached metrics.
* `matchday_number` (Integer, Nullable): Identifies the game week / matchday number (e.g., `1` through `38` in the Premier League).
* `api_id` (String, Nullable): External fixture API ID.
* **Uniqueness**: The global unique constraint on `Fixture.api_id` is replaced with a composite unique constraint `uq_fixture_tournament_api` on `(tournament_id, api_id)` to prevent identifier clashes between legacy World Cup IDs and API-Football IDs.

#### `tournament_teams` (TournamentTeam)
Associates a team with a specific tournament edition.
* `division` (String, Nullable): Used for nested divisional brackets (e.g., `"A"`, `"B"`, `"C"`, `"D"` in the Nations League).
* `promoted` / `relegated` (Boolean): Boolean flags denoting divisional moves.
* **Standings Cache**: Standings parameters (`points`, `wins`, `draws`, `losses`, `goals_for`, and `goals_against`) are cached directly on this table to prevent expensive N+1 query calculations during standings page serving.

#### `fixture_dependencies` (FixtureDependency) — [NEW]
Models tournament bracket graphs dynamically to map knockout bracket progression.
* `source_fixture_id` (Integer, ForeignKey): Source match ID.
* `target_fixture_id` (Integer, ForeignKey): Target match ID.
* `slot` (String): Target slot for the qualified team (`"home"` or `"away"`).
* `result_type` (String): Progression driver (`"winner"` or `"loser"`).

---

## 2. Database Migrations (Alembic)

All schema changes must be versioned and migrated via Alembic.

### 2.1 Applying Migrations
To upgrade the database to the latest schema, run:
```bash
python -m alembic upgrade head
```

### 2.2 SQLite Batch Migration Notice
Due to SQLite's structural constraints (lack of direct support for `ALTER COLUMN`, dropping indexes, or adding constraints on existing tables), all migration revisions modifying constraints or column nullability must use Alembic's `batch_alter_table` context:
```python
with op.batch_alter_table('teams', schema=None) as batch_op:
    batch_op.drop_index('ix_teams_name')
    batch_op.create_index('ix_teams_name', ['name'], unique=False)
```
Do not apply plain `op.alter_column` or `op.drop_constraint` statements to SQLite tables directly.

---

## 3. Seeding & Data Ingestion Workflows

Seeding new league/cup structures is a three-step command-line process.

### Step 3.1: Seed Teams & Squad Spotlight Players
To fetch and seed teams (e.g. Premier League, league=39, season=2026):
```bash
python -m backend.ingestor fetch-teams --league=39 --season=2026
```
This fetches teams from API-Football, inserts them as `"Club"` entities, and seeds up to 3 spotlight players (1 Goalkeeper, 1 Midfielder, 1 Forward) from active squads.

### Step 3.2: Verify and Import ELO Mappings (ClubElo)
Since ClubElo uses distinct team spellings, ELO integration uses a fuzzy-matched verification flow.

1. **Generate review file**:
   ```bash
   python -m backend.ingestor review-elo-matches
   ```
   Generates a JSON review list at `backend/data/elo_name_review.json` fuzzy matching DB clubs against ClubElo. Match confidences below `0.85` are marked `"needs_review"`.
   
2. **Review and approve**:
   Open `elo_name_review.json` and change the `"status"` of correct matches to `"approved"`. Correct any club name mismatches manually (e.g. mapping `"Nottingham Forest"` to `"Forest"`).
   
3. **Commit approved mappings**:
   ```bash
   python -m backend.ingestor apply-elo-matches --file=backend/data/elo_name_review.json
   ```
   Writes ELOs and logs `EloHistory` in the database for approved entries.

### Step 3.3: Seed Fixtures & Matchdays
Once teams and ELOs are loaded, fixtures can be seeded (idempotently):
```bash
python -m backend.ingestor seed-competition --league=39 --season=2026 --comp-name="Premier League" --comp-type="League" --format-engine="league"
```
This creates the tournament edition, loads game weeks, and calculates default ELO-weighted odds (incorporating ELO home advantages if `neutral_venue=False`). Running this multiple times updates existing fixture results and statuses without duplicate inserts.

