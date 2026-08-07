import sqlite3

conn = sqlite3.connect('football_games.db')
cursor = conn.cursor()

print("--- Competitions ---")
for row in cursor.execute("SELECT id, name, type, api_league_id FROM competitions").fetchall():
    print(row)

print("\n--- Tournaments ---")
for row in cursor.execute("SELECT id, competition_id, season_name, status FROM tournaments").fetchall():
    print(row)

print("\n--- Fixtures in Aug 2026 ---")
query = """
SELECT f.id, c.name, f.date_utc, ht.name, at.name, f.status
FROM fixtures f
JOIN tournaments t ON f.tournament_id = t.id
JOIN competitions c ON t.competition_id = c.id
JOIN teams ht ON f.home_team_id = ht.id
JOIN teams at ON f.away_team_id = at.id
WHERE f.date_utc >= '2026-08-01' AND f.date_utc <= '2026-08-31'
"""
rows = cursor.execute(query).fetchall()
print(f"Total fixtures in Aug 2026: {len(rows)}")
for r in rows[:20]:
    print(r)

print("\n--- Sample dates from Premier League ---")
query_pl = """
SELECT f.id, f.date_utc, ht.name, at.name
FROM fixtures f
JOIN tournaments t ON f.tournament_id = t.id
JOIN competitions c ON t.competition_id = c.id
JOIN teams ht ON f.home_team_id = ht.id
JOIN teams at ON f.away_team_id = at.id
WHERE c.name = 'Premier League'
ORDER BY f.date_utc ASC
LIMIT 10
"""
for r in cursor.execute(query_pl).fetchall():
    print(r)
