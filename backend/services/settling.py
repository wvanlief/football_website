from typing import Optional
from backend.database import Fixture, Team

def update_team_streaks(home_team: Team, away_team: Team, outcome: float):
    """
    Updates win, draw, and loss streak counters for both home and away teams.
    outcome: 1.0 for home win, 0.0 for away win, 0.5 for draw.
    """
    if outcome == 1.0:  # Home Win
        home_team.win_streak += 1
        home_team.draw_streak = 0
        home_team.loss_streak = 0
        
        away_team.loss_streak += 1
        away_team.win_streak = 0
        away_team.draw_streak = 0
    elif outcome == 0.0:  # Away Win
        away_team.win_streak += 1
        away_team.draw_streak = 0
        away_team.loss_streak = 0
        
        home_team.loss_streak += 1
        home_team.win_streak = 0
        home_team.draw_streak = 0
    else:  # Draw
        home_team.draw_streak += 1
        home_team.win_streak = 0
        home_team.loss_streak = 0
        
        away_team.draw_streak += 1
        away_team.win_streak = 0
        away_team.loss_streak = 0

def settle_result(fixture: Fixture, home_score: Optional[int], away_score: Optional[int]) -> None:
    """
    Settles a completed fixture by updating scores, status, winner, placeholders, and team streaks.
    """
    fixture.status = "Finished"
    fixture.home_score = home_score
    fixture.away_score = away_score

    home_team = fixture.home_team
    away_team = fixture.away_team

    if home_team and away_team:
        fixture.home_team_id = home_team.id
        fixture.away_team_id = away_team.id
        fixture.home_team_placeholder = None
        fixture.away_team_placeholder = None

        if home_score is not None and away_score is not None:
            if home_score > away_score:
                outcome = 1.0
                fixture.winner_id = home_team.id
            elif home_score < away_score:
                outcome = 0.0
                fixture.winner_id = away_team.id
            else:
                outcome = 0.5
                fixture.winner_id = None

            update_team_streaks(home_team, away_team, outcome)
        else:
            fixture.winner_id = None
    else:
        if home_score is not None and away_score is not None:
            if home_score > away_score:
                fixture.winner_id = fixture.home_team_id
            elif home_score < away_score:
                fixture.winner_id = fixture.away_team_id
            else:
                fixture.winner_id = None
        else:
            fixture.winner_id = None
