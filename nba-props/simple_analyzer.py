"""
Simple Stats-Based Prop Analysis
No ML - just find lines that deviate most from expected based on:
1. Player's season average
2. Player's last 5 games average
3. Opponent's defense (what they allow)

Theory: When Vegas line is WAY OFF from expected = they know something
        → Follow the deviation (bet the over if line is lower than expected, etc.)
"""
import sys
from datetime import date
from typing import Dict, List, Optional
import statistics
import pandas as pd

sys.path.insert(0, '/home/user/claamp-poll/nba-props')

from database.db import SessionLocal
from database.models import Team, Player, Game, PropLine
from services.nba_api_client import NBAAPIClient


class SimplePropsAnalyzer:
    """
    Simple statistical analysis for props
    No machine learning - just averages and deviations
    """

    def __init__(self):
        self.nba_client = NBAAPIClient()
        self.db = SessionLocal()

    def get_player_season_avg(self, player_id: int, stat_type: str, season: str = "2024-25") -> Optional[float]:
        """
        Get player's season average for a stat

        Args:
            player_id: NBA player ID
            stat_type: 'points', 'rebounds', 'assists', etc.
            season: Season string (e.g., "2024-25")

        Returns:
            Season average or None
        """
        game_log = self.nba_client.get_player_game_log(player_id, season)

        if game_log is None or game_log.empty:
            return None

        # Map stat_type to NBA API column name
        stat_map = {
            'points': 'PTS',
            'rebounds': 'REB',
            'assists': 'AST',
            'steals': 'STL',
            'blocks': 'BLK',
            'turnovers': 'TOV',
            'threes': 'FG3M'
        }

        col = stat_map.get(stat_type)
        if not col or col not in game_log.columns:
            return None

        return game_log[col].mean()

    def get_player_recent_avg(self, player_id: int, stat_type: str, last_n_games: int = 5, season: str = "2024-25") -> Optional[float]:
        """
        Get player's average over last N games

        Args:
            player_id: NBA player ID
            stat_type: 'points', 'rebounds', 'assists', etc.
            last_n_games: Number of recent games (default 5)
            season: Season string

        Returns:
            Recent average or None
        """
        game_log = self.nba_client.get_player_game_log(player_id, season)

        if game_log is None or game_log.empty:
            return None

        stat_map = {
            'points': 'PTS',
            'rebounds': 'REB',
            'assists': 'AST',
            'steals': 'STL',
            'blocks': 'BLK',
            'turnovers': 'TOV',
            'threes': 'FG3M'
        }

        col = stat_map.get(stat_type)
        if not col or col not in game_log.columns:
            return None

        # Get last N games
        recent_games = game_log.head(last_n_games)

        if recent_games.empty:
            return None

        return recent_games[col].mean()

    def get_opponent_defense(self, opponent_team_abbr: str, stat_type: str, season: str = "2024-25") -> Optional[float]:
        """
        Get how much this defense ALLOWS per game for a stat

        Args:
            opponent_team_abbr: Team abbreviation (e.g., 'LAL', 'BOS')
            stat_type: 'points', 'rebounds', 'assists', etc.
            season: Season string

        Returns:
            Average allowed per game or None
        """
        # For now, return league average as placeholder
        # In full implementation, would calculate actual team defense stats

        league_averages = {
            'points': 25.0,   # League avg points allowed per player
            'rebounds': 8.5,
            'assists': 6.0,
            'steals': 1.2,
            'blocks': 0.8,
            'turnovers': 2.5,
            'threes': 2.2
        }

        # TODO: Implement actual team defense stats
        # For now, just return league average
        return league_averages.get(stat_type)

    def calculate_expected_value(
        self,
        player_id: int,
        stat_type: str,
        opponent_team_abbr: str,
        season: str = "2024-25"
    ) -> Dict:
        """
        Calculate expected value based on:
        - Season average (40% weight)
        - Recent average (40% weight)
        - Opponent defense (20% weight)

        Returns:
            Dict with season_avg, recent_avg, opp_defense, expected, std_dev
        """
        season_avg = self.get_player_season_avg(player_id, stat_type, season)
        recent_avg = self.get_player_recent_avg(player_id, stat_type, 5, season)
        opp_defense = self.get_opponent_defense(opponent_team_abbr, stat_type, season)

        if season_avg is None or recent_avg is None:
            return None

        # Weighted average
        # 40% season avg, 40% recent form, 20% opponent defense
        expected = (season_avg * 0.4) + (recent_avg * 0.4) + (opp_defense * 0.2)

        # Calculate standard deviation from game log for uncertainty measure
        game_log = self.nba_client.get_player_game_log(player_id, season)

        stat_map = {
            'points': 'PTS',
            'rebounds': 'REB',
            'assists': 'AST',
            'steals': 'STL',
            'blocks': 'BLK',
            'turnovers': 'TOV',
            'threes': 'FG3M'
        }

        col = stat_map.get(stat_type)
        std_dev = game_log[col].std() if col in game_log.columns else None

        return {
            'season_avg': round(season_avg, 1),
            'recent_avg': round(recent_avg, 1),
            'opp_defense': round(opp_defense, 1) if opp_defense else None,
            'expected': round(expected, 1),
            'std_dev': round(std_dev, 1) if std_dev else None
        }

    def analyze_prop_line(
        self,
        player_id: int,
        player_name: str,
        stat_type: str,
        line_value: float,
        opponent_team_abbr: str,
        season: str = "2024-25"
    ) -> Dict:
        """
        Analyze a prop line and calculate deviation

        Returns:
            Dict with analysis including deviation from expected
        """
        expected_data = self.calculate_expected_value(
            player_id, stat_type, opponent_team_abbr, season
        )

        if not expected_data:
            return None

        expected = expected_data['expected']
        std_dev = expected_data['std_dev']

        # Calculate deviation
        deviation = line_value - expected

        # Calculate z-score (how many standard deviations off)
        z_score = deviation / std_dev if std_dev and std_dev > 0 else 0

        # Determine recommendation
        # If line is LOWER than expected → Vegas thinks they'll underperform → Bet UNDER
        # If line is HIGHER than expected → Vegas thinks they'll overperform → Bet OVER

        # We want BIGGEST deviations (Vegas knows something!)
        abs_z_score = abs(z_score)

        if abs_z_score < 0.5:
            recommendation = "NO PLAY"
            confidence = "Low"
        elif abs_z_score < 1.0:
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
            'reasoning': self._generate_reasoning(deviation, z_score, expected_data)
        }

    def _generate_reasoning(self, deviation: float, z_score: float, expected_data: Dict) -> str:
        """Generate human-readable reasoning"""
        season_avg = expected_data['season_avg']
        recent_avg = expected_data['recent_avg']

        if abs(z_score) < 0.5:
            return "Line is close to expected - no edge"

        if deviation < 0:
            # Line is LOWER than expected
            if recent_avg < season_avg:
                return f"Vegas set line LOW ({abs(deviation):.1f} below expected). Player trending down (recent: {recent_avg} vs season: {season_avg}). Follow Vegas → UNDER"
            else:
                return f"Vegas set line LOW despite good recent form. They know something → UNDER"
        else:
            # Line is HIGHER than expected
            if recent_avg > season_avg:
                return f"Vegas set line HIGH (+{deviation:.1f} above expected). Player trending up (recent: {recent_avg} vs season: {season_avg}). Follow Vegas → OVER"
            else:
                return f"Vegas set line HIGH despite down recent form. They know something → OVER"

    def find_best_plays(
        self,
        game_date: date,
        min_z_score: float = 0.75
    ) -> List[Dict]:
        """
        Find all props with significant deviations for a given date

        Args:
            game_date: Date to analyze
            min_z_score: Minimum absolute z-score to consider (default 0.75 = 3/4 std dev)

        Returns:
            List of plays sorted by deviation (biggest first)
        """
        # Get today's prop lines from database
        prop_lines = (
            self.db.query(PropLine)
            .join(Game)
            .filter(Game.game_date == game_date)
            .filter(PropLine.is_latest == True)
            .all()
        )

        if not prop_lines:
            print(f"No prop lines found for {game_date}")
            return []

        plays = []

        for prop_line in prop_lines:
            player = self.db.query(Player).get(prop_line.player_id)
            game = self.db.query(Game).get(prop_line.game_id)

            if not player or not game:
                continue

            # Get opponent team
            home_team = self.db.query(Team).get(game.home_team_id)
            away_team = self.db.query(Team).get(game.away_team_id)

            # Determine if player is home or away (simplified - assume away for now)
            opponent_abbr = home_team.abbreviation if home_team else "UNK"

            # Analyze this prop
            analysis = self.analyze_prop_line(
                player_id=player.nba_player_id,
                player_name=player.full_name,
                stat_type=prop_line.prop_type,
                line_value=prop_line.line_value,
                opponent_team_abbr=opponent_abbr
            )

            if analysis and abs(analysis['z_score']) >= min_z_score:
                plays.append(analysis)

        # Sort by absolute z-score (biggest deviations first)
        plays.sort(key=lambda x: abs(x['z_score']), reverse=True)

        return plays

    def close(self):
        """Close database connection"""
        self.db.close()


# ============================================================
# TEST SCRIPT
# ============================================================

if __name__ == "__main__":
    print("\n" + "="*70)
    print("  SIMPLE STATS-BASED PROP ANALYZER")
    print("  Find lines that deviate most from expected")
    print("="*70 + "\n")

    analyzer = SimplePropsAnalyzer()

    # Test with LeBron James
    print("TEST: Analyzing LeBron James prop\n")

    # Simulate a prop line
    analysis = analyzer.analyze_prop_line(
        player_id=2544,  # LeBron
        player_name="LeBron James",
        stat_type="points",
        line_value=22.5,  # Simulated line
        opponent_team_abbr="BOS"
    )

    if analysis:
        print(f"Player: {analysis['player_name']}")
        print(f"Prop: {analysis['stat_type']} O/U {analysis['line_value']}")
        print(f"\nStats:")
        print(f"  Season Avg: {analysis['season_avg']}")
        print(f"  Recent Avg (L5): {analysis['recent_avg']}")
        print(f"  Opponent Defense: {analysis['opp_defense']}")
        print(f"  Expected Value: {analysis['expected']}")
        print(f"\nDeviation Analysis:")
        print(f"  Deviation: {analysis['deviation']:+.1f}")
        print(f"  Z-Score: {analysis['z_score']:+.2f}")
        print(f"  Std Dev: {analysis['std_dev']}")
        print(f"\nRECOMMENDATION: {analysis['recommendation']} ({analysis['confidence']} confidence)")
        print(f"Reasoning: {analysis['reasoning']}")
    else:
        print("Could not analyze prop (missing data)")

    print("\n" + "="*70)

    analyzer.close()
