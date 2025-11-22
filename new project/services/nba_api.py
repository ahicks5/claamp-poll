"""
NBA API Client
Fetch player stats and game data
"""
import time
from typing import List, Dict, Optional
from datetime import date
import pandas as pd
from nba_api.stats.endpoints import playergamelog, commonallplayers, scoreboard
from nba_api.stats.static import teams


class NBAAPIClient:
    """Simple NBA API client"""

    def __init__(self):
        self.request_delay = 0.6  # Rate limiting

    def _delay(self):
        """Rate limit requests"""
        time.sleep(self.request_delay)

    def get_all_teams(self) -> List[Dict]:
        """Get all NBA teams"""
        return teams.get_teams()

    def get_all_players(self) -> pd.DataFrame:
        """Get all active players"""
        self._delay()
        players = commonallplayers.CommonAllPlayers(
            is_only_current_season=1
        ).get_data_frames()[0]
        return players

    def get_player_game_log(self, player_id: int, season: str = "2024-25") -> pd.DataFrame:
        """
        Get game-by-game stats for a player

        Returns DataFrame with columns:
        - GAME_DATE, MATCHUP, PTS, REB, AST, STL, BLK, TOV, MIN, etc.
        """
        self._delay()

        try:
            game_log = playergamelog.PlayerGameLog(
                player_id=player_id,
                season=season
            ).get_data_frames()[0]

            return game_log
        except Exception as e:
            print(f"Error fetching game log for player {player_id}: {e}")
            return pd.DataFrame()

    def get_games_for_date(self, game_date: date) -> List[Dict]:
        """
        Get all games for a specific date

        Returns list of dicts with:
        - game_id, home_team, away_team, game_date, status
        """
        self._delay()

        try:
            scoreboard_data = scoreboard.Scoreboard(
                game_date=game_date.strftime('%Y-%m-%d')
            ).get_data_frames()[0]

            games = []
            for _, game in scoreboard_data.iterrows():
                games.append({
                    'game_id': game['GAME_ID'],
                    'home_team_id': game['HOME_TEAM_ID'],
                    'away_team_id': game['VISITOR_TEAM_ID'],
                    'game_date': game_date,
                    'status': game['GAME_STATUS_TEXT']
                })

            return games

        except Exception as e:
            print(f"Error fetching games for {game_date}: {e}")
            return []
