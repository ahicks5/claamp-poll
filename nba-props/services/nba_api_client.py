# services/nba_api_client.py
"""Client for fetching NBA stats using the nba_api library."""
import os
import time
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from nba_api.stats.static import players, teams
from nba_api.stats.endpoints import (
    playergamelog,
    leaguegamefinder,
    commonplayerinfo,
    scoreboardv2
)
from nba_api.live.nba.endpoints import scoreboard
import pandas as pd

logger = logging.getLogger(__name__)


class NBAAPIClient:
    """Client for interacting with the NBA API."""

    def __init__(self):
        self.user_agent = os.getenv(
            "NBA_API_USER_AGENT",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        # Rate limiting - NBA API is unofficial and can block aggressive requests
        self.request_delay = 0.6  # 600ms between requests to be safe
        self.timeout = int(os.getenv("NBA_API_TIMEOUT", "90"))  # 90 second timeout for Heroku
        self.max_retries = int(os.getenv("NBA_API_MAX_RETRIES", "2"))

        # Configure nba_api library defaults
        self._configure_nba_api()

    def _configure_nba_api(self):
        """Configure nba_api library for Heroku compatibility."""
        try:
            from nba_api.stats.library.http import NBAStatsHTTP
            # Increase timeout for Heroku's slower network
            NBAStatsHTTP.timeout = self.timeout
            logger.info(f"NBA API configured with {self.timeout}s timeout")
        except Exception as e:
            logger.warning(f"Could not configure NBAStatsHTTP timeout: {e}")

    def _rate_limit(self):
        """Enforce rate limiting between requests."""
        time.sleep(self.request_delay)

    def _retry_request(self, func, *args, **kwargs):
        """Retry a request with exponential backoff."""
        kwargs['timeout'] = self.timeout

        for attempt in range(self.max_retries + 1):
            try:
                if attempt > 0:
                    wait_time = 2 ** attempt  # Exponential backoff: 2s, 4s, 8s
                    logger.info(f"Retry {attempt}/{self.max_retries} after {wait_time}s...")
                    time.sleep(wait_time)

                return func(*args, **kwargs)

            except Exception as e:
                if attempt == self.max_retries:
                    logger.error(f"Failed after {self.max_retries} retries: {e}")
                    raise
                logger.warning(f"Request failed (attempt {attempt + 1}), retrying: {e}")

    def get_all_teams(self) -> List[Dict]:
        """
        Get all NBA teams.

        Returns:
            List of team dictionaries with id, full_name, abbreviation, etc.
        """
        logger.info("Fetching all NBA teams...")
        self._rate_limit()

        try:
            teams_data = teams.get_teams()
            logger.info(f"Found {len(teams_data)} teams")
            return teams_data
        except Exception as e:
            logger.error(f"Error fetching teams: {e}")
            raise

    def get_all_active_players(self) -> List[Dict]:
        """
        Get all active NBA players.

        Returns:
            List of player dictionaries with id, full_name, is_active, etc.
        """
        logger.info("Fetching all active NBA players...")
        self._rate_limit()

        try:
            all_players = players.get_active_players()
            logger.info(f"Found {len(all_players)} active players")
            return all_players
        except Exception as e:
            logger.error(f"Error fetching players: {e}")
            raise

    def get_player_info(self, player_id: int) -> Dict:
        """
        Get detailed player information.

        Args:
            player_id: NBA API player ID

        Returns:
            Dictionary with player details (team, position, height, weight, etc.)
        """
        logger.debug(f"Fetching info for player {player_id}...")
        self._rate_limit()

        try:
            player_info = self._retry_request(
                commonplayerinfo.CommonPlayerInfo,
                player_id=player_id
            )
            df = player_info.get_data_frames()[0]

            if df.empty:
                logger.warning(f"No info found for player {player_id}")
                return {}

            return df.iloc[0].to_dict()
        except Exception as e:
            logger.error(f"Error fetching player info for {player_id}: {e}")
            return {}

    def get_player_game_log(
        self,
        player_id: int,
        season: str = "2024-25",
        season_type: str = "Regular Season"
    ) -> pd.DataFrame:
        """
        Get game-by-game stats for a player in a specific season.

        Args:
            player_id: NBA API player ID
            season: Season string (e.g., "2024-25")
            season_type: "Regular Season" or "Playoffs"

        Returns:
            DataFrame with game logs (points, rebounds, assists, etc. per game)
        """
        logger.debug(f"Fetching game log for player {player_id}, season {season}...")
        self._rate_limit()

        try:
            gamelog = self._retry_request(
                playergamelog.PlayerGameLog,
                player_id=player_id,
                season=season,
                season_type_all_star=season_type
            )
            df = gamelog.get_data_frames()[0]
            logger.debug(f"Found {len(df)} games for player {player_id}")
            return df
        except Exception as e:
            logger.error(f"Error fetching game log for player {player_id}: {e}")
            return pd.DataFrame()

    def get_todays_games(self) -> List[Dict]:
        """
        Get all games scheduled for today.

        Returns:
            List of game dictionaries with team IDs, game IDs, status, etc.
        """
        logger.info("Fetching today's games...")
        self._rate_limit()

        try:
            # Use the live scoreboard endpoint for current day
            board = scoreboard.ScoreBoard()
            games_data = board.games.get_dict()

            logger.info(f"Found {len(games_data)} games today")
            return games_data
        except Exception as e:
            logger.warning(f"Error with live scoreboard, trying legacy endpoint: {e}")
            # Fallback to legacy scoreboardv2
            return self._get_todays_games_legacy()

    def _get_todays_games_legacy(self) -> List[Dict]:
        """Fallback method using legacy ScoreboardV2 endpoint."""
        self._rate_limit()

        try:
            today = datetime.now().strftime("%Y-%m-%d")
            board = scoreboardv2.ScoreboardV2(game_date=today)
            df = board.get_data_frames()[0]  # GameHeader dataframe

            if df.empty:
                logger.info("No games found for today")
                return []

            games = df.to_dict('records')
            logger.info(f"Found {len(games)} games today (legacy)")
            return games
        except Exception as e:
            logger.error(f"Error fetching today's games (legacy): {e}")
            return []

    def get_games_for_date(self, date: datetime) -> List[Dict]:
        """
        Get all games for a specific date.

        Args:
            date: Date to fetch games for

        Returns:
            List of game dictionaries
        """
        logger.info(f"Fetching games for {date.strftime('%Y-%m-%d')}...")
        self._rate_limit()

        try:
            date_str = date.strftime("%Y-%m-%d")
            board = scoreboardv2.ScoreboardV2(game_date=date_str)
            df = board.get_data_frames()[0]

            if df.empty:
                logger.info(f"No games found for {date_str}")
                return []

            games = df.to_dict('records')
            logger.info(f"Found {len(games)} games for {date_str}")
            return games
        except Exception as e:
            logger.error(f"Error fetching games for {date_str}: {e}")
            return []

    def get_game_box_score(self, game_id: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Get box score (player stats) for a completed game.

        Args:
            game_id: NBA game ID

        Returns:
            Tuple of (player_stats_df, team_stats_df)
        """
        logger.debug(f"Fetching box score for game {game_id}...")
        self._rate_limit()

        try:
            from nba_api.stats.endpoints import boxscoretraditionalv2

            boxscore = boxscoretraditionalv2.BoxScoreTraditionalV2(game_id=game_id)
            dfs = boxscore.get_data_frames()

            player_stats = dfs[0]  # PlayerStats
            team_stats = dfs[1]    # TeamStats

            logger.debug(f"Got box score for game {game_id}: {len(player_stats)} player entries")
            return player_stats, team_stats
        except Exception as e:
            logger.error(f"Error fetching box score for game {game_id}: {e}")
            return pd.DataFrame(), pd.DataFrame()

    def search_player_by_name(self, name: str) -> Optional[Dict]:
        """
        Search for a player by name (fuzzy matching).

        Args:
            name: Player name to search for

        Returns:
            Player dictionary if found, None otherwise
        """
        logger.debug(f"Searching for player: {name}")
        self._rate_limit()

        try:
            # Get all players (both active and inactive for comprehensive search)
            all_players = players.get_players()

            # Try exact match first
            for player in all_players:
                if player['full_name'].lower() == name.lower():
                    logger.debug(f"Found exact match: {player['full_name']}")
                    return player

            # Try partial match
            for player in all_players:
                if name.lower() in player['full_name'].lower():
                    logger.debug(f"Found partial match: {player['full_name']}")
                    return player

            logger.warning(f"No player found matching: {name}")
            return None
        except Exception as e:
            logger.error(f"Error searching for player {name}: {e}")
            return None

    def get_season_string(self, year: int = None) -> str:
        """
        Get NBA season string for a given year.
        NBA season spans two years (e.g., 2024-25 season runs Oct 2024 - June 2025).

        Args:
            year: Year to get season for (defaults to current year)

        Returns:
            Season string (e.g., "2024-25")
        """
        if year is None:
            now = datetime.now()
            year = now.year
            # If we're before October, we're still in the previous season
            if now.month < 10:
                year -= 1

        return f"{year}-{str(year + 1)[-2:]}"
