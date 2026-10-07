import numpy as np
import pandas as pd
from collections import defaultdict, Counter
import random
import time

# ====================== CONFIG ======================
NUM_SIMULATIONS = 30000  # Adjust based on your machine (video used ~100k)
HOME_ADVANTAGE = 80      # Slightly lower for neutral venues, higher for hosts
K_FACTOR = 30
BASE_LAMBDA = 1.35

# ====================== ELO DATA ======================
# Use real data from eloratings.net (as of May 2026)
ELO_RATINGS = {
    "Spain": 2165, "Argentina": 2113, "France": 2082, "England": 2020,
    "Brazil": 1984, "Portugal": 1984, "Colombia": 1975, "Netherlands": 1961,
    "Germany": 1923, "Norway": 1912, "Japan": 1904, "Turkey": 1902,
    "Uruguay": 1892, "Switzerland": 1889, "Senegal": 1878, "Mexico": 1858,
    "USA": 1721, "Canada": 1784, "Morocco": 1821, "Algeria": 1743,
    "Croatia": 1930, "Ecuador": 1933, "Austria": 1827, "Paraguay": 1833,
    "South Korea": 1752, "Australia": 1783, "Scotland": 1767,
    "Iran": 1760, "Uzbekistan": 1727, "Qatar": 1600,  # approximate lower ones
    "South Africa": 1650, "Haiti": 1550, "Curaçao": 1500, "Cape Verde": 1580,
    # Add remaining teams with reasonable values (you can expand this)
    "Panama": 1737, "Ghana": 1680, "New Zealand": 1550, "Jordan": 1690,
    # Playoff placeholders can use average Elo ~1700 or resolve them
}

# ====================== 2026 GROUPS (from FIFA Draw) ======================
# Placeholders for playoff winners are noted
GROUPS = {
    "A": ["Mexico", "South Africa", "South Korea", "Czechia"],  # or Denmark etc.
    "B": ["Canada", "Switzerland", "Qatar", "Bosnia and Herzegovina"],  # approx
    "C": ["Brazil", "Morocco", "Scotland", "Haiti"],
    "D": ["USA", "Paraguay", "Australia", "Turkey"],  # approx playoff
    "E": ["Germany", "Ecuador", "Curaçao", "Côte d'Ivoire"],
    "F": ["Netherlands", "Japan", "Tunisia", "Poland"],  # approx
    "G": ["Belgium", "Egypt", "Iran", "New Zealand"],
    "H": ["Spain", "Uruguay", "Saudi Arabia", "Cape Verde"],
    "I": ["France", "Senegal", "Norway", "Iraq"],  # approx
    "J": ["Argentina", "Algeria", "Austria", "Jordan"],
    "K": ["Portugal", "Colombia", "Uzbekistan", "Jamaica"],  # approx
    "L": ["England", "Croatia", "Panama", "Ghana"],
}

def get_elo(team):
    return ELO_RATINGS.get(team, 1650)  # default for unknowns

# ====================== MATCH SIM ======================
def simulate_match(team_a, team_b, elo_a, elo_b, is_home_a=False):
    home_adv = HOME_ADVANTAGE if is_home_a else 0
    p_a = 1 / (1 + 10**((elo_b - elo_a - home_adv) / 400.0))
    
    lambda_a = BASE_LAMBDA * (p_a / 0.46)
    lambda_b = BASE_LAMBDA * ((1 - p_a) / 0.46)
    
    goals_a = np.random.poisson(lambda_a)
    goals_b = np.random.poisson(lambda_b)
    
    # Elo update
    expected_a = p_a
    actual_a = 1 if goals_a > goals_b else 0.5 if goals_a == goals_b else 0
    change = K_FACTOR * (actual_a - expected_a)
    
    new_elo_a = elo_a + change
    new_elo_b = elo_b - change
    
    if goals_a > goals_b:
        winner = team_a
    elif goals_b > goals_a:
        winner = team_b
    else:
        winner = random.choice([team_a, team_b])  # tiebreaker for knockout later
    
    return {
        "goals_a": goals_a, "goals_b": goals_b, "winner": winner,
        "new_elo_a": new_elo_a, "new_elo_b": new_elo_b
    }

# ====================== GROUP STAGE ======================
def simulate_group_stage(groups, base_elo):
    current_elo = base_elo.copy()
    group_standings = {}
    all_thirds = []
    
    for group_name, teams in groups.items():
        standings = {team: {"pts": 0, "gf": 0, "ga": 0, "gd": 0, "matches": []} for team in teams}
        
        # Play all matches in group
        for i in range(4):
            for j in range(i+1, 4):
                a, b = teams[i], teams[j]
                res = simulate_match(a, b, current_elo[a], current_elo[b])
                
                # Update standings
                if res["goals_a"] > res["goals_b"]:
                    standings[a]["pts"] += 3
                elif res["goals_b"] > res["goals_a"]:
                    standings[b]["pts"] += 3
                else:
                    standings[a]["pts"] += 1
                    standings[b]["pts"] += 1
                
                standings[a]["gf"] += res["goals_a"]
                standings[a]["ga"] += res["goals_b"]
                standings[b]["gf"] += res["goals_b"]
                standings[b]["ga"] += res["goals_a"]
                
                current_elo[a] = res["new_elo_a"]
                current_elo[b] = res["new_elo_b"]
        
        # Calculate GD
        for team in standings:
            standings[team]["gd"] = standings[team]["gf"] - standings[team]["ga"]
        
        # Sort group
        sorted_standings = sorted(standings.items(), 
                                  key=lambda x: (-x[1]["pts"], -x[1]["gd"], -x[1]["gf"]))
        
        group_standings[group_name] = sorted_standings
        
        # Collect top 2 + 3rd
        all_thirds.append((group_name, sorted_standings[2][1]))  # 3rd place
    
    # Select 8 best thirds
    best_thirds = sorted(all_thirds, key=lambda x: (-x[1]["pts"], -x[1]["gd"], -x[1]["gf"]))[:8]
    
    # Advancing teams
    advancing = []
    for g in group_standings.values():
        advancing.extend([g[0][0], g[1][0]])  # 1st and 2nd
    advancing.extend([t[0] for t in best_thirds])
    
    return advancing, current_elo

# ====================== KNOCKOUT STAGE (SIMPLIFIED) ======================
def simulate_knockout(advancing_teams, current_elo):
    active = advancing_teams[:]
    random.shuffle(active)  # Random bracket for each sim (or implement fixed bracket)
    
    while len(active) > 1:
        next_round = []
        for i in range(0, len(active) - 1, 2):
            if i + 1 >= len(active):
                next_round.append(active[i])
                continue
            a, b = active[i], active[i+1]
            res = simulate_match(a, b, current_elo[a], current_elo[b])
            next_round.append(res["winner"])
            current_elo[a] = res["new_elo_a"]
            current_elo[b] = res["new_elo_b"]
        active = next_round
    return active[0]

# ====================== FULL MONTE CARLO ======================
def run_monte_carlo(num_sims=NUM_SIMULATIONS):
    champions = Counter()
    start = time.time()
    
    for sim in range(num_sims):
        if sim % 5000 == 0 and sim > 0:
            print(f"Progress: {sim}/{num_sims} ({sim/num_sims*100:.1f}%)")
        
        advancing, elo_after_groups = simulate_group_stage(GROUPS, ELO_RATINGS)
        champion = simulate_knockout(advancing, elo_after_groups)
        champions[champion] += 1
    
    elapsed = time.time() - start
    print(f"Completed {num_sims} simulations in {elapsed:.1f} seconds")
    
    df = pd.DataFrame({
        "Team": list(champions.keys()),
        "Titles": list(champions.values()),
        "Probability_%": [100 * v / num_sims for v in champions.values()]
    }).sort_values("Titles", ascending=False)
    
    return df

if __name__ == "__main__":
    results = run_monte_carlo()
    print(results.head(15))
    results.to_csv("wc2026_monte_carlo_results.csv", index=False)
	
	
import numpy as np
from collections import defaultdict

# ====================== PLAYER & MANAGER DATABASE ======================
class Player:
    def __init__(self, name, rating, position, age, form=0.0):
        self.name = name
        self.rating = rating      # 0-100 scale
        self.position = position  # 'GK', 'DEF', 'MID', 'ATT'
        self.age = age
        self.form = form          # -10 to +10 recent form adjustment

class Manager:
    def __init__(self, name, bonus):
        self.name = name
        self.bonus = bonus  # e.g., 3-8 points for elite coaches

# Example squads (expand with real projected 2026 squads)
SQUADS = {
    "France": {
        "manager": Manager("Didier Deschamps / Successor", 7),
        "starting_xi": [
            Player("Mbappé", 94, "ATT", 27, 2),
            Player("Bellingham-like", 90, "MID", 26, 1),  # e.g. Camavinga or Tchouameni
            # ... add full XI
        ],
        "bench_depth": 82,   # average rating of top substitutes
    },
    "Argentina": {
        "manager": Manager("Scaloni / Successor", 6),
        "starting_xi": [Player("Messi", 88, "ATT", 39, 1), ...],
        "bench_depth": 80,
    },
    # Add all 48 teams (this is the data-heavy part)
}

def calculate_team_strength(squad, formation_bonus=0):
    """Compute dynamic team rating"""
    if not squad["starting_xi"]:
        return 1650  # fallback
    
    # Weighted average: attackers & midfielders slightly higher weight
    weights = {'GK': 0.8, 'DEF': 1.0, 'MID': 1.1, 'ATT': 1.2}
    total_weight = 0
    weighted_sum = 0
    
    for p in squad["starting_xi"]:
        w = weights.get(p.position, 1.0)
        weighted_sum += (p.rating + p.form) * w
        total_weight += w
    
    avg_starting = weighted_sum / total_weight
    team_rating = (avg_starting * 0.75 + squad["bench_depth"] * 0.25)
    
    # Manager & formation effect
    team_rating += squad["manager"].bonus + formation_bonus
    return team_rating

# ====================== UPDATED MATCH SIM ======================
def simulate_match_composition(team_a, team_b, is_home_a=False):
    strength_a = calculate_team_strength(SQUADS[team_a])
    strength_b = calculate_team_strength(SQUADS[team_b])
    
    home_adv = 80 if is_home_a else 0
    p_a = 1 / (1 + 10**((strength_b - strength_a - home_adv) / 400.0))
    
    # Poisson goals (same as before)
    lambda_a = 1.35 * (p_a / 0.46)
    lambda_b = 1.35 * ((1 - p_a) / 0.46)
    
    goals_a = np.random.poisson(lambda_a)
    goals_b = np.random.poisson(lambda_b)
    
    # Winner + small individual player updates (optional)
    if goals_a > goals_b:
        winner = team_a
        # Example: boost top scorer's form
    elif goals_b > goals_a:
        winner = team_b
    else:
        winner = random.choice([team_a, team_b])
    
    return {
        "goals_a": goals_a,
        "goals_b": goals_b,
        "winner": winner,
        "strength_a": strength_a,
        "strength_b": strength_b
    }

# In your group_stage / knockout functions, replace get_elo(team) with calculate_team_strength(SQUADS[team])
