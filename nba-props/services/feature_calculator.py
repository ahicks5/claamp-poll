# services/feature_calculator.py
"""Feature engineering for NBA player props predictions."""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from database import Player, Game, PlayerGameStats, PropLine


class FeatureCalculator:
    """Calculate features for ML model."""

    def __init__(self, session: Session):
        self.session = session

    def calculate_player_features(
        self,
        player_id: int,
        game_date: datetime.date,
        prop_type: str = 'points',
        lookback_games: int = 20
    ) -> Dict:
        """
        Calculate all features for a player on a specific date.

        Args:
            player_id: Player ID
            game_date: Date of the game to predict
            prop_type: Type of prop (points, rebounds, assists, etc.)
            lookback_games: Number of previous games to consider

        Returns:
            Dictionary of features
        """
        features = {}

        # Get player's recent games (before game_date)
        recent_games = self._get_recent_games(player_id, game_date, lookback_games)

        if not recent_games:
            return None

        # Calculate rolling statistics
        features.update(self._calculate_rolling_stats(recent_games, prop_type))

        # Calculate trend features
        features.update(self._calculate_trends(recent_games, prop_type))

        # Calculate home/away splits
        features.update(self._calculate_home_away_splits(recent_games, prop_type))

        # Calculate rest days
        features['days_rest'] = self._calculate_rest_days(recent_games)

        # Calculate minutes trends
        features.update(self._calculate_minutes_features(recent_games))

        # Get opponent features
        # (This would need the upcoming game info)

        return features

    def calculate_prop_line_features(
        self,
        player_id: int,
        game_id: int,
        prop_type: str,
        current_line: float
    ) -> Dict:
        """
        Calculate features related to the prop line itself.

        Args:
            player_id: Player ID
            game_id: Game ID
            prop_type: Type of prop
            current_line: Current line value

        Returns:
            Dictionary of line-related features
        """
        features = {}

        # Get historical lines for this player/prop type
        historical_lines = self._get_historical_lines(player_id, prop_type, limit=10)

        if historical_lines:
            # Calculate line movement
            features['line_vs_avg'] = current_line - np.mean(historical_lines)
            features['line_vs_recent'] = current_line - np.mean(historical_lines[-5:])

            # Line movement volatility
            if len(historical_lines) > 1:
                features['line_std'] = np.std(historical_lines)
                features['line_movement'] = historical_lines[-1] - historical_lines[-2]
            else:
                features['line_std'] = 0
                features['line_movement'] = 0

            # Sharp line movement detection (Vegas trap indicator)
            if len(historical_lines) >= 5:
                recent_avg = np.mean(historical_lines[-5:])
                features['sharp_movement'] = abs(current_line - recent_avg)
                # Flag if line moved more than 2.5 (sharp movement)
                features['is_sharp_movement'] = 1 if features['sharp_movement'] > 2.5 else 0
            else:
                features['sharp_movement'] = 0
                features['is_sharp_movement'] = 0

        return features

    def calculate_streak_features(
        self,
        player_id: int,
        game_date: datetime.date,
        prop_type: str = 'points'
    ) -> Dict:
        """
        Calculate streak-based features (hitting over/under consecutively).

        Args:
            player_id: Player ID
            game_date: Game date
            prop_type: Type of prop

        Returns:
            Dictionary of streak features
        """
        features = {}

        # Get recent games with prop lines
        games_with_props = self._get_games_with_props(player_id, game_date, prop_type, limit=15)

        if not games_with_props:
            return {
                'over_streak': 0,
                'under_streak': 0,
                'hit_rate_last_5': 0.5,
                'hit_rate_last_10': 0.5
            }

        # Calculate streaks
        current_streak = 0
        streak_type = None

        for game in games_with_props:
            actual = game['actual']
            line = game['line']

            if actual is None or line is None:
                break

            hit_over = actual > line

            if streak_type is None:
                streak_type = 'over' if hit_over else 'under'
                current_streak = 1
            elif (streak_type == 'over' and hit_over) or (streak_type == 'under' and not hit_over):
                current_streak += 1
            else:
                break

        features['over_streak'] = current_streak if streak_type == 'over' else 0
        features['under_streak'] = current_streak if streak_type == 'under' else 0

        # Calculate hit rates
        if len(games_with_props) >= 5:
            last_5 = games_with_props[:5]
            overs = sum(1 for g in last_5 if g['actual'] > g['line'])
            features['hit_rate_last_5'] = overs / 5
        else:
            features['hit_rate_last_5'] = 0.5

        if len(games_with_props) >= 10:
            last_10 = games_with_props[:10]
            overs = sum(1 for g in last_10 if g['actual'] > g['line'])
            features['hit_rate_last_10'] = overs / 10
        else:
            features['hit_rate_last_10'] = 0.5

        # Line adjustment after streak (Vegas reaction)
        if len(games_with_props) >= 2:
            features['line_change_after_streak'] = games_with_props[0]['line'] - games_with_props[1]['line']
        else:
            features['line_change_after_streak'] = 0

        return features

    def _get_recent_games(
        self,
        player_id: int,
        before_date: datetime.date,
        limit: int
    ) -> List[PlayerGameStats]:
        """Get player's recent games before a specific date."""
        games = self.session.query(PlayerGameStats).join(Game).filter(
            PlayerGameStats.player_id == player_id,
            Game.game_date < before_date,
            Game.status == 'final'
        ).order_by(Game.game_date.desc()).limit(limit).all()

        return games

    def _calculate_rolling_stats(
        self,
        games: List[PlayerGameStats],
        prop_type: str
    ) -> Dict:
        """Calculate rolling averages and statistics."""
        features = {}

        # Get stat values
        stat_values = [self._get_stat_value(g, prop_type) for g in games]
        stat_values = [v for v in stat_values if v is not None]

        if not stat_values:
            return {}

        # Different window sizes
        for window in [3, 5, 10, 15]:
            if len(stat_values) >= window:
                window_values = stat_values[:window]
                features[f'{prop_type}_avg_last_{window}'] = np.mean(window_values)
                features[f'{prop_type}_std_last_{window}'] = np.std(window_values)
                features[f'{prop_type}_max_last_{window}'] = np.max(window_values)
                features[f'{prop_type}_min_last_{window}'] = np.min(window_values)
                features[f'{prop_type}_median_last_{window}'] = np.median(window_values)

                # Trend: is performance increasing or decreasing?
                if window >= 5:
                    recent_avg = np.mean(window_values[:window//2])
                    older_avg = np.mean(window_values[window//2:])
                    features[f'{prop_type}_trend_last_{window}'] = recent_avg - older_avg

        # Overall average
        features[f'{prop_type}_season_avg'] = np.mean(stat_values)

        return features

    def _calculate_trends(self, games: List[PlayerGameStats], prop_type: str) -> Dict:
        """Calculate trend-based features."""
        features = {}

        stat_values = [self._get_stat_value(g, prop_type) for g in games]
        stat_values = [v for v in stat_values if v is not None]

        if len(stat_values) < 5:
            return {}

        # Momentum: last 3 vs previous 3
        if len(stat_values) >= 6:
            last_3 = np.mean(stat_values[:3])
            prev_3 = np.mean(stat_values[3:6])
            features[f'{prop_type}_momentum'] = last_3 - prev_3

        # Consistency (coefficient of variation)
        features[f'{prop_type}_consistency'] = np.std(stat_values) / np.mean(stat_values) if np.mean(stat_values) > 0 else 0

        # Games over season average (form indicator)
        season_avg = np.mean(stat_values)
        recent_5 = stat_values[:5]
        games_over_avg = sum(1 for v in recent_5 if v > season_avg)
        features[f'{prop_type}_games_over_avg_last_5'] = games_over_avg

        return features

    def _calculate_home_away_splits(
        self,
        games: List[PlayerGameStats],
        prop_type: str
    ) -> Dict:
        """Calculate home vs away performance splits."""
        features = {}

        home_games = []
        away_games = []

        for game_stat in games:
            game = self.session.query(Game).get(game_stat.game_id)
            if not game:
                continue

            stat_value = self._get_stat_value(game_stat, prop_type)
            if stat_value is None:
                continue

            player = self.session.query(Player).get(game_stat.player_id)
            if not player:
                continue

            # Determine if home or away
            if player.team_id == game.home_team_id:
                home_games.append(stat_value)
            else:
                away_games.append(stat_value)

        # Calculate splits
        if home_games:
            features[f'{prop_type}_home_avg'] = np.mean(home_games)
            features[f'{prop_type}_home_games'] = len(home_games)
        else:
            features[f'{prop_type}_home_avg'] = 0
            features[f'{prop_type}_home_games'] = 0

        if away_games:
            features[f'{prop_type}_away_avg'] = np.mean(away_games)
            features[f'{prop_type}_away_games'] = len(away_games)
        else:
            features[f'{prop_type}_away_avg'] = 0
            features[f'{prop_type}_away_games'] = 0

        # Home/away differential
        if home_games and away_games:
            features[f'{prop_type}_home_away_diff'] = features[f'{prop_type}_home_avg'] - features[f'{prop_type}_away_avg']
        else:
            features[f'{prop_type}_home_away_diff'] = 0

        return features

    def _calculate_rest_days(self, games: List[PlayerGameStats]) -> int:
        """Calculate days of rest before most recent game."""
        if len(games) < 2:
            return 3  # Default

        most_recent = self.session.query(Game).get(games[0].game_id)
        previous = self.session.query(Game).get(games[1].game_id)

        if most_recent and previous:
            delta = most_recent.game_date - previous.game_date
            return delta.days
        return 3

    def _calculate_minutes_features(self, games: List[PlayerGameStats]) -> Dict:
        """Calculate features related to playing time."""
        features = {}

        minutes = [g.minutes for g in games if g.minutes is not None]

        if not minutes:
            return {}

        # Average minutes
        features['minutes_avg'] = np.mean(minutes)
        features['minutes_std'] = np.std(minutes)

        # Recent minutes trend
        if len(minutes) >= 5:
            recent_3 = np.mean(minutes[:3])
            prev_3 = np.mean(minutes[3:6]) if len(minutes) >= 6 else features['minutes_avg']
            features['minutes_trend'] = recent_3 - prev_3
        else:
            features['minutes_trend'] = 0

        # Minutes consistency (important for props)
        if len(minutes) >= 5:
            last_5 = minutes[:5]
            features['minutes_consistency'] = 1 - (np.std(last_5) / np.mean(last_5)) if np.mean(last_5) > 0 else 0
        else:
            features['minutes_consistency'] = 0

        return features

    def _get_historical_lines(
        self,
        player_id: int,
        prop_type: str,
        limit: int = 10
    ) -> List[float]:
        """Get historical prop lines for a player."""
        lines = self.session.query(PropLine.line_value).filter(
            PropLine.player_id == player_id,
            PropLine.prop_type == prop_type,
            PropLine.is_latest == True
        ).order_by(PropLine.fetched_at.desc()).limit(limit).all()

        return [line[0] for line in lines]

    def _get_games_with_props(
        self,
        player_id: int,
        before_date: datetime.date,
        prop_type: str,
        limit: int = 15
    ) -> List[Dict]:
        """Get games with both actual stats and prop lines."""
        results = []

        # Get recent completed games
        games = self.session.query(Game).join(PlayerGameStats).filter(
            PlayerGameStats.player_id == player_id,
            Game.game_date < before_date,
            Game.status == 'final'
        ).order_by(Game.game_date.desc()).limit(limit).all()

        for game in games:
            # Get player stats
            stats = self.session.query(PlayerGameStats).filter(
                PlayerGameStats.player_id == player_id,
                PlayerGameStats.game_id == game.id
            ).first()

            if not stats:
                continue

            # Get prop line
            prop = self.session.query(PropLine).filter(
                PropLine.player_id == player_id,
                PropLine.game_id == game.id,
                PropLine.prop_type == prop_type
            ).first()

            if not prop:
                continue

            actual = self._get_stat_value(stats, prop_type)

            results.append({
                'game_date': game.game_date,
                'actual': actual,
                'line': prop.line_value,
                'hit_over': actual > prop.line_value if actual is not None else None
            })

        return results

    def _get_stat_value(self, stats: PlayerGameStats, prop_type: str) -> Optional[float]:
        """Extract the relevant stat value based on prop type."""
        if prop_type == 'points':
            return stats.points
        elif prop_type == 'rebounds':
            return stats.rebounds
        elif prop_type == 'assists':
            return stats.assists
        elif prop_type == 'steals':
            return stats.steals
        elif prop_type == 'blocks':
            return stats.blocks
        elif prop_type == 'threes':
            return stats.three_pointers_made
        elif prop_type == 'pts_reb_ast':
            pts = stats.points or 0
            reb = stats.rebounds or 0
            ast = stats.assists or 0
            return pts + reb + ast
        elif prop_type == 'pts_reb':
            pts = stats.points or 0
            reb = stats.rebounds or 0
            return pts + reb
        elif prop_type == 'pts_ast':
            pts = stats.points or 0
            ast = stats.assists or 0
            return pts + ast
        elif prop_type == 'reb_ast':
            reb = stats.rebounds or 0
            ast = stats.assists or 0
            return reb + ast
        else:
            return None
