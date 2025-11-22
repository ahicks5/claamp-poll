"""
Odds API Client
Fetch prop lines from sportsbooks
"""
import os
import requests
from typing import List, Dict, Optional
from datetime import datetime, timedelta


class OddsAPIClient:
    """Simple Odds API client"""

    BASE_URL = "https://api.the-odds-api.com/v4"
    SPORT = "basketball_nba"

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("ODDS_API_KEY")
        if not self.api_key:
            raise ValueError("ODDS_API_KEY not found")

    def get_upcoming_games(self, days_ahead: int = 1) -> List[Dict]:
        """
        Get upcoming NBA games with odds

        Returns list of games with event IDs
        """
        url = f"{self.BASE_URL}/sports/{self.SPORT}/odds"

        params = {
            'apiKey': self.api_key,
            'regions': 'us',
            'markets': 'h2h',
            'oddsFormat': 'american'
        }

        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()

            games = response.json()

            # Filter by date
            cutoff = datetime.now() + timedelta(days=days_ahead)
            upcoming = []

            for game in games:
                commence_time = datetime.fromisoformat(
                    game['commence_time'].replace('Z', '+00:00')
                )
                if commence_time <= cutoff:
                    upcoming.append(game)

            return upcoming

        except Exception as e:
            print(f"Error fetching upcoming games: {e}")
            return []

    def get_player_props(self, event_id: str) -> Optional[Dict]:
        """
        Get player props for a specific game

        Returns props data with bookmakers and markets
        """
        url = f"{self.BASE_URL}/sports/{self.SPORT}/events/{event_id}/odds"

        params = {
            'apiKey': self.api_key,
            'regions': 'us',
            'markets': 'player_points,player_rebounds,player_assists,player_threes,player_steals,player_blocks',
            'oddsFormat': 'american'
        }

        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response.json()

        except Exception as e:
            print(f"Error fetching props for {event_id}: {e}")
            return None
