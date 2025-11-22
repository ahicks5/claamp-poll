"""
Simple Stats-Based Prop Analyzer

Calculate expected values based on:
1. Player's season average (40% weight)
2. Player's last 5 games average (40% weight)
3. Opponent defense allowed (20% weight)

Find deviations from Vegas lines
"""
from typing import Dict, Optional
import statistics
from services.nba_api import NBAAPIClient


class PropAnalyzer:
    """Simple statistical prop analyzer"""

    def __init__(self):
        self.nba_client = NBAAPIClient()

    def get_season_avg(self, player_id: int, stat_type: str, season: str = "2024-25") -> Optional[float]:
        """Get player's season average for a stat"""
        game_log = self.nba_client.get_player_game_log(player_id, season)

        if game_log.empty:
            return None

        stat_map = {
            'points': 'PTS',
            'rebounds': 'REB',
            'assists': 'AST',
            'steals': 'STL',
            'blocks': 'BLK',
            'threes': 'FG3M'
        }

        col = stat_map.get(stat_type)
        if not col or col not in game_log.columns:
            return None

        return game_log[col].mean()

    def get_recent_avg(self, player_id: int, stat_type: str, last_n: int = 5, season: str = "2024-25") -> Optional[float]:
        """Get player's average over last N games"""
        game_log = self.nba_client.get_player_game_log(player_id, season)

        if game_log.empty:
            return None

        stat_map = {
            'points': 'PTS',
            'rebounds': 'REB',
            'assists': 'AST',
            'steals': 'STL',
            'blocks': 'BLK',
            'threes': 'FG3M'
        }

        col = stat_map.get(stat_type)
        if not col or col not in game_log.columns:
            return None

        recent = game_log.head(last_n)
        if recent.empty:
            return None

        return recent[col].mean()

    def get_opponent_defense(self, opponent_abbr: str, stat_type: str) -> float:
        """
        Get how much this defense allows

        TODO: Calculate real team defense stats
        For now, returns league average
        """
        league_avg = {
            'points': 25.0,
            'rebounds': 8.5,
            'assists': 6.0,
            'steals': 1.2,
            'blocks': 0.8,
            'threes': 2.2
        }

        return league_avg.get(stat_type, 0.0)

    def calculate_expected(
        self,
        player_id: int,
        stat_type: str,
        opponent_abbr: str,
        season: str = "2024-25"
    ) -> Optional[Dict]:
        """
        Calculate expected value

        Weights:
        - 40% season average
        - 40% recent average (last 5)
        - 20% opponent defense

        Returns dict with season_avg, recent_avg, opp_defense, expected, std_dev
        """
        season_avg = self.get_season_avg(player_id, stat_type, season)
        recent_avg = self.get_recent_avg(player_id, stat_type, 5, season)
        opp_defense = self.get_opponent_defense(opponent_abbr, stat_type)

        if season_avg is None or recent_avg is None:
            return None

        # Weighted average
        expected = (season_avg * 0.4) + (recent_avg * 0.4) + (opp_defense * 0.2)

        # Get standard deviation for z-score calculation
        game_log = self.nba_client.get_player_game_log(player_id, season)

        stat_map = {
            'points': 'PTS',
            'rebounds': 'REB',
            'assists': 'AST',
            'steals': 'STL',
            'blocks': 'BLK',
            'threes': 'FG3M'
        }

        col = stat_map.get(stat_type)
        std_dev = game_log[col].std() if col in game_log.columns else None

        return {
            'season_avg': round(season_avg, 1),
            'recent_avg': round(recent_avg, 1),
            'opp_defense': round(opp_defense, 1),
            'expected': round(expected, 1),
            'std_dev': round(std_dev, 1) if std_dev else None
        }

    def analyze_prop(
        self,
        player_id: int,
        player_name: str,
        stat_type: str,
        line_value: float,
        opponent_abbr: str,
        season: str = "2024-25"
    ) -> Optional[Dict]:
        """
        Analyze a prop line

        Returns analysis with deviation and recommendation
        """
        expected_data = self.calculate_expected(player_id, stat_type, opponent_abbr, season)

        if not expected_data:
            return None

        expected = expected_data['expected']
        std_dev = expected_data['std_dev']

        # Calculate deviation
        deviation = line_value - expected

        # Z-score (how many std devs away)
        z_score = deviation / std_dev if std_dev and std_dev > 0 else 0

        # Recommendation based on deviation
        abs_z = abs(z_score)

        if abs_z < 0.5:
            recommendation = "NO PLAY"
            confidence = "Low"
        elif abs_z < 1.0:
            recommendation = "UNDER" if deviation < 0 else "OVER"
            confidence = "Medium"
        else:
            recommendation = "UNDER" if deviation < 0 else "OVER"
            confidence = "High"

        return {
            'player_name': player_name,
            'stat_type': stat_type,
            'line_value': line_value,
            'season_avg': expected_data['season_avg'],
            'recent_avg': expected_data['recent_avg'],
            'opp_defense': expected_data['opp_defense'],
            'expected': expected,
            'deviation': round(deviation, 1),
            'z_score': round(z_score, 2),
            'std_dev': std_dev,
            'recommendation': recommendation,
            'confidence': confidence,
            'reasoning': self._get_reasoning(deviation, z_score, expected_data)
        }

    def _get_reasoning(self, deviation: float, z_score: float, expected_data: Dict) -> str:
        """Generate reasoning for recommendation"""
        if abs(z_score) < 0.5:
            return "Line is close to expected - no edge"

        season_avg = expected_data['season_avg']
        recent_avg = expected_data['recent_avg']

        if deviation < 0:
            # Line is LOW
            if recent_avg < season_avg:
                return f"Vegas set line LOW. Player trending down (recent: {recent_avg} vs season: {season_avg}). Follow Vegas → UNDER"
            else:
                return f"Vegas set line LOW despite good recent form. They know something → UNDER"
        else:
            # Line is HIGH
            if recent_avg > season_avg:
                return f"Vegas set line HIGH. Player trending up (recent: {recent_avg} vs season: {season_avg}). Follow Vegas → OVER"
            else:
                return f"Vegas set line HIGH despite down recent form. They know something → OVER"
