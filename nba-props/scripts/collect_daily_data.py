#!/usr/bin/env python3
# scripts/collect_daily_data.py
"""Daily data collection: fetch today's games, props, and update stats."""
import sys
import os
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional

# Add parent directory to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from database import get_session, Team, Player, Game, PropLine, PlayerGameStats
from services.nba_api_client import NBAAPIClient
from services.odds_api_client import OddsAPIClient

# Configure logging with proper path
LOG_DIR = os.path.join(PROJECT_ROOT, 'logs')
os.makedirs(LOG_DIR, exist_ok=True)  # Create logs directory if it doesn't exist

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(LOG_DIR, 'daily_collection.log'))
    ]
)
logger = logging.getLogger(__name__)


class DailyDataCollector:
    """Handles daily data collection workflow."""

    def __init__(self):
        self.nba_client = NBAAPIClient()
        self.odds_client = OddsAPIClient()
        self.session = get_session()

    def run(self, days_ahead: int = 1):
        """
        Run the full daily collection workflow.

        Args:
            days_ahead: Number of days ahead to collect (1 = today only)
        """
        logger.info("=" * 60)
        logger.info("Daily Data Collection")
        logger.info("=" * 60)
        logger.info(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("")

        try:
            # Step 1: Fetch upcoming games from Odds API
            logger.info("Step 1: Fetching upcoming games from Odds API...")
            upcoming_games = self.odds_client.get_upcoming_games(days_ahead=days_ahead)
            logger.info(f"✓ Found {len(upcoming_games)} upcoming games\n")

            if not upcoming_games:
                logger.info("No upcoming games found. Exiting.")
                return

            # Step 2: Create game records and fetch player props
            logger.info("Step 2: Processing games and fetching player props...")
            games_created = 0
            props_collected = 0

            for game_data in upcoming_games:
                event_id = game_data['id']
                home_team_name = game_data['home_team']
                away_team_name = game_data['away_team']
                commence_time = datetime.fromisoformat(game_data['commence_time'].replace('Z', '+00:00'))

                logger.info(f"\n  Game: {away_team_name} @ {home_team_name}")
                logger.info(f"  Time: {commence_time.strftime('%Y-%m-%d %H:%M')}")

                # Find teams in our database (fuzzy matching may be needed)
                home_team = self._find_team_by_name(home_team_name)
                away_team = self._find_team_by_name(away_team_name)

                if not home_team or not away_team:
                    logger.warning(f"  ✗ Could not match teams in database")
                    continue

                # Create or get game
                game = self._create_or_get_game(
                    event_id=event_id,
                    home_team=home_team,
                    away_team=away_team,
                    commence_time=commence_time
                )

                if not game:
                    logger.warning(f"  ✗ Could not create game record")
                    continue

                games_created += 1
                logger.info(f"  ✓ Game record created (ID: {game.id})")

                # Fetch player props for this game
                logger.info(f"  Fetching player props...")
                props_data = self.odds_client.get_player_props(event_id)

                if props_data:
                    parsed_props = self.odds_client.parse_player_props(props_data)
                    logger.info(f"  Found {len(parsed_props)} prop lines")

                    # Store props
                    props_added = self._store_prop_lines(game, parsed_props)
                    props_collected += props_added
                    logger.info(f"  ✓ Stored {props_added} prop lines")
                else:
                    logger.info(f"  No props available yet")

            # Commit all changes
            self.session.commit()

            # Step 3: Show API usage
            logger.info("\n" + "=" * 60)
            logger.info("Collection Summary")
            logger.info("=" * 60)
            logger.info(f"Games processed: {games_created}")
            logger.info(f"Prop lines collected: {props_collected}")

            usage = self.odds_client.get_api_usage()
            logger.info(f"\nOdds API Usage:")
            logger.info(f"  Requests used (this session): {usage['requests_used']}")
            if usage['requests_remaining']:
                logger.info(f"  Requests remaining: {usage['requests_remaining']}")

            logger.info("\n✓ Daily collection complete!")
            logger.info("=" * 60)

        except Exception as e:
            logger.error(f"\n✗ Error during collection: {e}")
            self.session.rollback()
            raise

    def update_completed_games(self):
        """Update stats for games that have finished."""
        logger.info("\nUpdating completed games...")

        # Find games that are final but might need updated stats
        recent_games = self.session.query(Game).filter(
            Game.status == 'final',
            Game.game_date >= datetime.now().date() - timedelta(days=2)
        ).all()

        logger.info(f"Found {len(recent_games)} recent completed games")

        stats_updated = 0

        for game in recent_games:
            try:
                # Fetch box score
                player_stats_df, _ = self.nba_client.get_game_box_score(game.nba_game_id)

                if player_stats_df.empty:
                    continue

                # Update player stats
                for _, row in player_stats_df.iterrows():
                    player_id = row.get('PLAYER_ID')
                    if not player_id:
                        continue

                    # Find player in our database
                    player = self.session.query(Player).filter_by(nba_player_id=player_id).first()
                    if not player:
                        continue

                    # Create or update stats
                    existing_stats = self.session.query(PlayerGameStats).filter_by(
                        player_id=player.id,
                        game_id=game.id
                    ).first()

                    if not existing_stats:
                        stats = PlayerGameStats(
                            player_id=player.id,
                            game_id=game.id,
                            minutes=row.get('MIN'),
                            points=row.get('PTS'),
                            rebounds=row.get('REB'),
                            assists=row.get('AST'),
                            # ... other stats
                        )
                        self.session.add(stats)
                        stats_updated += 1

                self.session.commit()

            except Exception as e:
                logger.error(f"Error updating game {game.nba_game_id}: {e}")
                continue

        logger.info(f"✓ Updated {stats_updated} player stat records")

    def _find_team_by_name(self, team_name: str) -> Optional[Team]:
        """
        Find team in database by name (with fuzzy matching).

        Args:
            team_name: Team name from Odds API

        Returns:
            Team object or None
        """
        # Try exact match first
        team = self.session.query(Team).filter(Team.name == team_name).first()
        if team:
            return team

        # Try partial match
        team = self.session.query(Team).filter(Team.name.like(f"%{team_name}%")).first()
        if team:
            return team

        # Try matching just the city
        for team in self.session.query(Team).all():
            if team.city and team.city in team_name:
                return team

        return None

    def _create_or_get_game(self, event_id: str, home_team: Team, away_team: Team, commence_time: datetime) -> Optional[Game]:
        """Create or retrieve game record."""
        # Check if game exists (by teams and date)
        game_date = commence_time.date()

        existing = self.session.query(Game).filter(
            Game.home_team_id == home_team.id,
            Game.away_team_id == away_team.id,
            Game.game_date == game_date
        ).first()

        if existing:
            # Update game time if it changed
            if existing.game_time != commence_time:
                existing.game_time = commence_time
                self.session.flush()
            return existing

        # Create new game
        # Use event_id as nba_game_id (we'll update it later when we get the real NBA ID)
        game = Game(
            nba_game_id=f"odds_{event_id}",  # Prefix to avoid conflicts
            game_date=game_date,
            game_time=commence_time,
            season=self.nba_client.get_season_string(),
            home_team_id=home_team.id,
            away_team_id=away_team.id,
            status='scheduled'
        )

        self.session.add(game)
        self.session.flush()

        return game

    def _store_prop_lines(self, game: Game, parsed_props: List[Dict]) -> int:
        """
        Store prop lines in database.

        Args:
            game: Game object
            parsed_props: List of parsed prop dictionaries

        Returns:
            Number of props stored
        """
        props_stored = 0

        # Mark all existing props for this game as not latest
        self.session.query(PropLine).filter(
            PropLine.game_id == game.id,
            PropLine.is_latest == True
        ).update({'is_latest': False})

        for prop in parsed_props:
            player_name = prop['player_name']

            # Find player (fuzzy matching)
            player = self._find_player_by_name(player_name)

            if not player:
                logger.debug(f"    Could not find player: {player_name}")
                continue

            # Create prop line
            prop_line = PropLine(
                player_id=player.id,
                game_id=game.id,
                prop_type=prop['prop_type'],
                line_value=prop['line_value'],
                sportsbook=prop['sportsbook'],
                market_key=prop['market_key'],
                over_odds=prop.get('over_odds'),
                under_odds=prop.get('under_odds'),
                is_latest=True
            )

            self.session.add(prop_line)
            props_stored += 1

        return props_stored

    def _find_player_by_name(self, player_name: str) -> Optional[Player]:
        """Find player by name with fuzzy matching."""
        # Try exact match
        player = self.session.query(Player).filter(Player.full_name == player_name).first()
        if player:
            return player

        # Try case-insensitive
        player = self.session.query(Player).filter(
            Player.full_name.ilike(player_name)
        ).first()
        if player:
            return player

        # Try partial match
        player = self.session.query(Player).filter(
            Player.full_name.ilike(f"%{player_name}%")
        ).first()

        return player

    def close(self):
        """Close database session."""
        self.session.close()


def main():
    """Main entry point for daily collection."""
    import argparse

    parser = argparse.ArgumentParser(description='Collect daily NBA props data')
    parser.add_argument(
        '--days-ahead',
        type=int,
        default=1,
        help='Number of days ahead to collect (default: 1)'
    )
    parser.add_argument(
        '--update-completed',
        action='store_true',
        help='Also update stats for recently completed games'
    )

    args = parser.parse_args()

    collector = DailyDataCollector()

    try:
        # Run daily collection
        collector.run(days_ahead=args.days_ahead)

        # Optionally update completed games
        if args.update_completed:
            collector.update_completed_games()

    except KeyboardInterrupt:
        logger.info("\n\nCollection interrupted by user")
    except Exception as e:
        logger.error(f"\n\nCollection failed: {e}")
        raise
    finally:
        collector.close()


if __name__ == "__main__":
    main()
