import os
import json
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from backend.database import Team, Fixture, FixtureOdds, EloHistory
from backend.scoring import update_fixture_score
from backend.utils import fetch_url_with_retry
from backend.services.ingestion import NameNormalizer
from backend.services.odds import calculate_default_odds

def elo_to_form(elo: float) -> float:
    """
    Calculates form score from ELO rating, clamped between 45.0 and 95.0, rounded to 1 decimal place.
    Base form is 50.0 at 1500 ELO, scaling by 0.05 per ELO point.
    """
    if elo is None:
        elo = 1500.0
    return round(min(95.0, max(45.0, 50.0 + (float(elo) - 1500.0) * 0.05)), 1)

def fetch_current_elo_ratings() -> dict[str, int]:
    """
    Fetches current Elo ratings of international football teams from eloratings.net.
    Returns a dictionary mapping normalized team names to Elo ratings.
    """
    teams_url = "https://www.eloratings.net/en.teams.tsv"
    world_url = "https://www.eloratings.net/World.tsv"
    normalizer = NameNormalizer()
    
    teams_content = fetch_url_with_retry(teams_url, provider="eloratings").decode('utf-8')
        
    code_to_name = {}
    for line in teams_content.split('\n'):
        if not line.strip():
            continue
        parts = line.split('\t')
        if len(parts) >= 2:
            code = parts[0].strip()
            name = parts[1].strip()
            code_to_name[code] = normalizer.normalize(name)
            
    world_content = fetch_url_with_retry(world_url, provider="eloratings").decode('utf-8')
        
    parsed_ratings = {}
    for line in world_content.split('\n'):
        if not line.strip():
            continue
        parts = line.split('\t')
        if len(parts) >= 4:
            code = parts[2].strip()
            elo_str = parts[3].strip().replace('\u2212', '-')
            try:
                elo = int(elo_str)
                name = code_to_name.get(code)
                if name:
                    parsed_ratings[name] = elo
            except ValueError:
                pass
                
    return parsed_ratings

def fetch_clubelo_ratings(date_str: str = None) -> dict[str, int]:
    """Fetches Elo ratings of club teams from clubelo.com."""
    if not date_str:
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    url = f"http://api.clubelo.com/{date_str}"
    print(f"Fetching ClubElo CSV from: {url}")
    
    def _parse_csv(url_to_fetch: str) -> dict[str, int]:
        try:
            content = fetch_url_with_retry(url_to_fetch, provider="clubelo").decode('utf-8')
        except Exception as e:
            print(f"Error fetching ClubElo ratings from {url_to_fetch}: {e}")
            return {}
            
        res = {}
        lines = content.split('\n')
        if len(lines) < 2:
            return res
            
        for line in lines[1:]:
            if not line.strip():
                continue
            parts = line.split(',')
            if len(parts) >= 5:
                club_name = parts[1].strip()
                elo_str = parts[4].strip()
                try:
                    res[club_name] = int(float(elo_str))
                except ValueError:
                    pass
        return res

    ratings = _parse_csv(url)
    if "Bayern" not in ratings or len(ratings) < 500:
        print("Notice: Merging full ClubElo snapshot for complete coverage...")
        fallback_ratings = _parse_csv("http://api.clubelo.com/2025-05-25")
        for k, v in fallback_ratings.items():
            if k not in ratings:
                ratings[k] = v
            
    return ratings

def fuzzy_match_team(team_name: str, clubelo_names: list[str]) -> tuple[str, float]:
    """Fuzzy match team name against ClubElo name registry with fast exact-match short circuits."""
    if not team_name or not clubelo_names:
        return "", 0.0

    # 1. Fast exact & case-insensitive match
    t_lower = team_name.lower()
    for name in clubelo_names:
        if name.lower() == t_lower:
            return name, 1.0

    # 2. Try RapidFuzz if installed (C-accelerated)
    try:
        from rapidfuzz import process, fuzz
        match = process.extractOne(team_name, clubelo_names, scorer=fuzz.token_sort_ratio)
        if match:
            return match[0], match[1] / 100.0
    except ImportError:
        pass
        
    # 3. Fast substring check before difflib
    for name in clubelo_names:
        n_lower = name.lower()
        if t_lower in n_lower or n_lower in t_lower:
            return name, 0.90

    # 4. Fallback to difflib SequenceMatcher
    import difflib
    best_name = None
    best_score = 0.0
    for name in clubelo_names:
        score = difflib.SequenceMatcher(None, t_lower, name.lower()).ratio()
        if score > best_score:
            best_score = score
            best_name = name
            
    return best_name or "", best_score

def review_elo_matches(db: Session, output_path: str = "backend/data/elo_name_review.json"):
    """Generates an ELO match review file comparing DB club teams with ClubElo database."""
    teams = db.query(Team).filter(Team.team_type == "Club", Team.elo_source == "clubelo").all()
    if not teams:
        print("No club teams found in DB. Did you fetch teams first?")
        return
        
    clubelo_ratings = fetch_clubelo_ratings()
    if not clubelo_ratings:
        print("Failed to fetch ClubElo ratings.")
        return

    existing_map = {}
    if os.path.exists(output_path):
        try:
            with open(output_path, "r", encoding="utf-8") as f:
                existing_list = json.load(f)
                if isinstance(existing_list, list):
                    for item in existing_list:
                        api_name = item.get("api_football_name")
                        if api_name:
                            existing_map[api_name] = item
        except Exception as e:
            print(f"Warning: Could not parse existing review file {output_path}: {e}")

    clubelo_names = list(clubelo_ratings.keys())
    review_list = []
    
    for team in teams:
        prev_item = existing_map.get(team.name)
        if prev_item and prev_item.get("status") == "approved":
            c_name = prev_item.get("clubelo_name")
            elo_val = clubelo_ratings.get(c_name, prev_item.get("elo", 1500))
            review_list.append({
                "api_football_name": team.name,
                "clubelo_name": c_name,
                "confidence": prev_item.get("confidence", 1.0),
                "elo": elo_val,
                "status": "approved"
            })
        else:
            best_name, confidence = fuzzy_match_team(team.name, clubelo_names)
            elo_val = clubelo_ratings.get(best_name, 1500)
            status = "approved" if confidence >= 0.85 else "needs_review"
            
            review_list.append({
                "api_football_name": team.name,
                "clubelo_name": best_name,
                "confidence": round(confidence, 2),
                "elo": elo_val,
                "status": status
            })
        
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(review_list, f, indent=2, ensure_ascii=False)
        
    print(f"Generated ELO review file: {output_path}")

def record_elo_history(db: Session, team_id: int, elo_rating: int, recorded_at: datetime | None = None) -> EloHistory:
    """
    Records an EloHistory snapshot for a team, deduplicating by calendar date.
    If an entry already exists for the team on the same date, it updates the elo_rating rather than creating duplicates.
    """
    if recorded_at is None:
        recorded_at = datetime.now(timezone.utc)

    target_date = recorded_at.date() if isinstance(recorded_at, datetime) else recorded_at

    existing = db.query(EloHistory).filter(EloHistory.team_id == team_id).all()
    same_date_entry = None
    for entry in existing:
        if entry.recorded_at and entry.recorded_at.date() == target_date:
            same_date_entry = entry
            break

    if same_date_entry:
        same_date_entry.elo_rating = elo_rating
        same_date_entry.recorded_at = recorded_at
        return same_date_entry
    else:
        history = EloHistory(
            team_id=team_id,
            recorded_at=recorded_at,
            elo_rating=elo_rating
        )
        db.add(history)
        return history

def apply_elo_matches(db: Session, file_path: str):
    """Applies verified ELO mappings from elo_name_review.json to DB."""
    if not os.path.exists(file_path):
        print(f"ELO review file {file_path} not found.")
        return
        
    with open(file_path, "r", encoding="utf-8") as f:
        review_list = json.load(f)
        
    now_time = datetime.now(timezone.utc)
    count = 0
    for item in review_list:
        if item.get("status") == "approved":
            api_name = item.get("api_football_name")
            clubelo_name = item.get("clubelo_name")
            elo = item.get("elo")
            
            team = db.query(Team).filter(Team.name == api_name, Team.team_type == "Club").first()
            if team:
                team.elo = elo
                team.form_score = elo_to_form(elo)
                
                record_elo_history(db, team.id, elo, now_time)
                count += 1
                print(f"Applied ELO {elo} to {api_name} (mapped from {clubelo_name})")
                
    db.commit()
    print(f"Successfully applied ELO ratings to {count} teams.")

    all_fixtures = db.query(Fixture).all()
    print(f"Recalculating odds & watchability scores for {len(all_fixtures)} fixtures...")
    for f in all_fixtures:
        if f.home_team and f.away_team:
            comp = f.tournament.competition if f.tournament else None
            home_adv = comp.home_advantage_elo if (comp and comp.home_advantage_elo is not None) else 100
            neutral = comp.neutral_venue if comp else False
            
            h_odds, d_odds, a_odds = calculate_default_odds(
                f.home_team.elo or 1500, 
                f.away_team.elo or 1500, 
                neutral_venue=neutral, 
                home_advantage=home_adv
            )
            
            if f.latest_odds:
                f.latest_odds.odds_home = h_odds
                f.latest_odds.odds_draw = d_odds
                f.latest_odds.odds_away = a_odds
            else:
                new_odds = FixtureOdds(
                    fixture_id=f.id,
                    recorded_at=f.date_utc,
                    odds_home=h_odds,
                    odds_draw=d_odds,
                    odds_away=a_odds
                )
                db.add(new_odds)
                
            update_fixture_score(f, db)
            
    db.commit()
    print("Successfully updated default odds and watchability scores across all fixtures.")
