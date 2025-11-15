# services/odds_api_client.py
"""Client for fetching NBA player props from The Odds API."""
import os
import logging
import requests
from typing import List, Dict, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class OddsAPIClient:
    """Client for interacting with The Odds API."""

    BASE_URL = "https://api.the-odds-api.com/v4"
    SPORT = "basketball_nba"

    def __init__(self, api_key: str = None):
        """
        Initialize Odds API client.

        Args:
            api_key: The Odds API key (if not provided, reads from env)
        """
        self.api_key = api_key or os.getenv("ODDS_API_KEY")
        if not self.api_key:
            raise ValueError("ODDS_API_KEY not found in environment or provided")

        self.session = requests.Session()
        self.requests_used = 0
        self.requests_remaining = None

    def _make_request(self, endpoint: str, params: Dict = None) -> Optional[Dict]:
        """
        Make a request to the Odds API with error handling.

        Args:
            endpoint: API endpoint path
            params: Query parameters

        Returns:
            JSON response data or None on error
        """
        url = f"{self.BASE_URL}/{endpoint}"

        # Add API key to params
        if params is None:
            params = {}
        params['apiKey'] = self.api_key

        try:
            logger.debug(f"Making request to: {url}")
            response = self.session.get(url, params=params, timeout=30)

            # Track API usage from headers
            self.requests_used += 1
            if 'x-requests-remaining' in response.headers:
                self.requests_remaining = int(response.headers['x-requests-remaining'])
                logger.info(f"API requests remaining: {self.requests_remaining}")

            if 'x-requests-used' in response.headers:
                logger.debug(f"API requests used: {response.headers['x-requests-used']}")

            response.raise_for_status()
            return response.json()

        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error from Odds API: {e}")
            logger.error(f"Response: {response.text}")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return None

    def get_upcoming_games(self, days_ahead: int = 1) -> List[Dict]:
        """
        Get upcoming NBA games.

        Args:
            days_ahead: Number of days ahead to look for games

        Returns:
            List of game/event dictionaries
        """
        logger.info(f"Fetching upcoming NBA games (next {days_ahead} days)...")

        params = {
            'regions': 'us',
            'markets': 'h2h',  # Just need basic game info
            'oddsFormat': 'american',
        }

        data = self._make_request(f"sports/{self.SPORT}/odds", params=params)

        if not data:
            logger.warning("No upcoming games data returned")
            return []

        # Filter games within the specified days ahead
        from datetime import timezone
        cutoff = datetime.now(timezone.utc) + timedelta(days=days_ahead)
        upcoming_games = []

        for game in data:
            commence_time = datetime.fromisoformat(game['commence_time'].replace('Z', '+00:00'))
            if commence_time <= cutoff:
                upcoming_games.append(game)

        logger.info(f"Found {len(upcoming_games)} upcoming games")
        return upcoming_games

    def get_player_props(self, event_id: str, regions: str = 'us') -> Optional[Dict]:
        """
        Get player props for a specific game/event.

        Args:
            event_id: The event ID from get_upcoming_games()
            regions: Regions to get odds for (us, uk, eu, au)

        Returns:
            Dictionary with player prop markets or None
        """
        logger.info(f"Fetching player props for event {event_id}...")

        params = {
            'regions': regions,
            'markets': 'player_points,player_rebounds,player_assists,player_threes,player_blocks,player_steals,player_turnovers,player_points_rebounds_assists,player_points_rebounds,player_points_assists,player_rebounds_assists',
            'oddsFormat': 'american',
        }

        data = self._make_request(f"sports/{self.SPORT}/events/{event_id}/odds", params=params)

        if not data:
            logger.warning(f"No player props data returned for event {event_id}")
            return None

        logger.info(f"Got player props for event {event_id}")
        return data

    def get_all_player_props_for_today(self) -> List[Dict]:
        """
        Get player props for all games happening today.

        Returns:
            List of dictionaries containing game info and player props
        """
        logger.info("Fetching all player props for today's games...")

        # First, get upcoming games
        upcoming_games = self.get_upcoming_games(days_ahead=1)

        if not upcoming_games:
            logger.info("No games found for today")
            return []

        all_props = []

        for game in upcoming_games:
            event_id = game.get('id')
            if not event_id:
                continue

            # Get player props for this game
            props = self.get_player_props(event_id)

            if props:
                all_props.append({
                    'event_id': event_id,
                    'home_team': game.get('home_team'),
                    'away_team': game.get('away_team'),
                    'commence_time': game.get('commence_time'),
                    'props': props
                })

        logger.info(f"Fetched props for {len(all_props)} games")
        return all_props

    def parse_player_props(self, props_data: Dict) -> List[Dict]:
        """
        Parse raw player props data into a more usable format.

        Args:
            props_data: Raw data from get_player_props()

        Returns:
            List of parsed prop line dictionaries
        """
        parsed_props = []

        if not props_data or 'bookmakers' not in props_data:
            return parsed_props

        for bookmaker in props_data['bookmakers']:
            sportsbook = bookmaker['key']

            for market in bookmaker.get('markets', []):
                market_key = market['key']
                prop_type = self._normalize_prop_type(market_key)

                for outcome in market.get('outcomes', []):
                    # Player props have a 'description' field with the player name
                    player_name = outcome.get('description', outcome.get('name', ''))
                    point = outcome.get('point')  # The line value
                    price = outcome.get('price')  # The odds

                    if not player_name or point is None:
                        continue

                    # Determine if this is Over or Under
                    outcome_type = outcome.get('name', '').lower()

                    prop = {
                        'player_name': player_name,
                        'prop_type': prop_type,
                        'line_value': float(point),
                        'sportsbook': sportsbook,
                        'market_key': market_key,
                    }

                    if 'over' in outcome_type:
                        prop['over_odds'] = price
                    elif 'under' in outcome_type:
                        prop['under_odds'] = price

                    parsed_props.append(prop)

        logger.debug(f"Parsed {len(parsed_props)} player prop lines")
        return parsed_props

    def _normalize_prop_type(self, market_key: str) -> str:
        """
        Normalize market key to our internal prop type naming.

        Args:
            market_key: Market key from Odds API (e.g., 'player_points')

        Returns:
            Normalized prop type (e.g., 'points')
        """
        mapping = {
            'player_points': 'points',
            'player_rebounds': 'rebounds',
            'player_assists': 'assists',
            'player_threes': 'threes',
            'player_blocks': 'blocks',
            'player_steals': 'steals',
            'player_turnovers': 'turnovers',
            'player_points_rebounds_assists': 'pts_reb_ast',
            'player_points_rebounds': 'pts_reb',
            'player_points_assists': 'pts_ast',
            'player_rebounds_assists': 'reb_ast',
        }
        return mapping.get(market_key, market_key)

    def get_api_usage(self) -> Dict:
        """
        Get current API usage statistics.

        Returns:
            Dictionary with usage stats
        """
        return {
            'requests_used': self.requests_used,
            'requests_remaining': self.requests_remaining,
        }
