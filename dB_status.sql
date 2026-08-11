SELECT 'Competitions' AS entity, COUNT(*) AS total_count FROM competitions
UNION ALL
SELECT 'Tournaments', COUNT(*) FROM tournaments
UNION ALL
SELECT 'Teams', COUNT(*) FROM teams
UNION ALL
SELECT 'Tournament Teams', COUNT(*) FROM tournament_teams
UNION ALL
SELECT 'Fixtures', COUNT(*) FROM fixtures
UNION ALL
SELECT 'Players', COUNT(*) FROM players
UNION ALL
SELECT 'Fixture Odds Records', COUNT(*) FROM fixture_odds;

SELECT 
    c.name AS competition_name,
    t.season_name,
    t.status AS tournament_status,
    COUNT(DISTINCT tt.team_id) AS total_teams,
    COUNT(DISTINCT f.id) AS total_fixtures,
    COUNT(DISTINCT CASE WHEN f.status = 'Finished' THEN f.id END) AS finished_fixtures,
    COUNT(DISTINCT CASE WHEN f.status = 'Scheduled' THEN f.id END) AS scheduled_fixtures,
    COUNT(DISTINCT o.id) AS odds_records
FROM competitions c
LEFT JOIN tournaments t ON t.competition_id = c.id
LEFT JOIN tournament_teams tt ON tt.tournament_id = t.id
LEFT JOIN fixtures f ON f.tournament_id = t.id
LEFT JOIN fixture_odds o ON o.fixture_id = f.id
GROUP BY c.id, c.name, t.id, t.season_name, t.status
ORDER BY total_fixtures DESC;

SELECT 
    f.id,
    c.name AS competition,
    t.season_name,
    COALESCE(ht.name, f.home_team_placeholder) AS home_team,
    COALESCE(at.name, f.away_team_placeholder) AS away_team,
    f.stage,
    f.status,
    f.date_utc,
    f.watchability_score
FROM fixtures f
JOIN tournaments t ON f.tournament_id = t.id
JOIN competitions c ON t.competition_id = c.id
LEFT JOIN teams ht ON f.home_team_id = ht.id
LEFT JOIN teams at ON f.away_team_id = at.id
ORDER BY f.date_utc ASC
LIMIT 15;
