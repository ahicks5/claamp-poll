#!/usr/bin/env python3
# scripts/backfill_historical.py
"""Backfill historical NBA game data and player stats."""
import sys
import os
import logging
from datetime import datetime, timedelta
from typing import List

# Add parent directory to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# Load environment variables early
from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, '.env'))
load_dotenv(os.path.join(os.path.dirname(PROJECT_ROOT), '.env'))

from database import get_session, Team, Player, Game, PlayerGameStats
from services.nba_api_client import NBAAPIClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class HistoricalDataBackfill:
    """Handles backfilling historical NBA data."""

    def __init__(self):
        self.nba_client = NBAAPIClient()
        self.session = get_session()

    def backfill_season_games(self, season: str = "2024-25", limit: int = None):
        """
        Backfill games and player stats for an entire season.

        Args:
            season: Season string (e.g., "2024-25")
            limit: Optional limit on number of games to process (for testing)
        """
        logger.info(f"Starting backfill for {season} season...")

        # Get all active players
        players = self.session.query(Player).filter_by(is_active=True).all()
        logger.info(f"Found {len(players)} active players")

        games_processed = set()
        total_stats_added = 0

        for i, player in enumerate(players, 1):
            logger.info(f"Processing player {i}/{len(players)}: {player.full_name}")

            try:
                # Get game log for this player
                game_log = self.nba_client.get_player_game_log(
                    player_id=player.nba_player_id,
                    season=season
                )

                if game_log.empty:
                    logger.debug(f"  No games found for {player.full_name}")
                    continue

                logger.info(f"  Found {len(game_log)} games")

                # Process each game
                for _, game_row in game_log.iterrows():
                    # Extract game info
                    game_id = game_row.get('Game_ID')
                    game_date_str = game_row.get('GAME_DATE')

                    if not game_id or not game_date_str:
                        continue

                    # Parse game date
                    try:
                        game_date = datetime.strptime(game_date_str, '%b %d, %Y').date()
                    except:
                        try:
                            game_date = datetime.strptime(game_date_str, '%Y-%m-%d').date()
                        except:
                            logger.warning(f"  Could not parse date: {game_date_str}")
                            continue

                    # Create or get game
                    game = self._create_or_get_game(game_id, game_date, game_row, season)

                    if game and game.id:
                        games_processed.add(game_id)

                        # Create player game stats
                        stats_created = self._create_player_game_stats(player, game, game_row)
                        if stats_created:
                            total_stats_added += 1

                # Commit after each player to save progress
                self.session.commit()

                # Check limit
                if limit and len(games_processed) >= limit:
                    logger.info(f"Reached limit of {limit} games, stopping")
                    break

            except Exception as e:
                logger.error(f"  Error processing {player.full_name}: {e}")
                self.session.rollback()
                continue

        logger.info(f"\n{'='*60}")
        logger.info(f"Backfill complete!")
        logger.info(f"  Games processed: {len(games_processed)}")
        logger.info(f"  Player stats added: {total_stats_added}")
        logger.info(f"{'='*60}")

    def _create_or_get_game(self, game_id: str, game_date, game_row, season: str):
        """Create or retrieve a game record."""
        # Check if game already exists
        game = self.session.query(Game).filter_by(nba_game_id=game_id).first()

        if game:
            return game

        # Parse matchup to get teams (format: "LAL vs. BOS" or "LAL @ BOS")
        matchup = game_row.get('MATCHUP', '')

        try:
            if ' vs. ' in matchup:
                parts = matchup.split(' vs. ')
                home_abbr = parts[0].strip()
                away_abbr = parts[1].strip()
            elif ' @ ' in matchup:
                parts = matchup.split(' @ ')
                away_abbr = parts[0].strip()
                home_abbr = parts[1].strip()
            else:
                logger.warning(f"  Could not parse matchup: {matchup}")
                return None

            # Find teams
            home_team = self.session.query(Team).filter_by(abbreviation=home_abbr).first()
            away_team = self.session.query(Team).filter_by(abbreviation=away_abbr).first()

            if not home_team or not away_team:
                logger.warning(f"  Could not find teams: {home_abbr} vs {away_abbr}")
                return None

            # Determine game status
            wl = game_row.get('WL')  # W/L indicates game is complete
            status = 'final' if wl else 'scheduled'

            # Create game
            game = Game(
                nba_game_id=game_id,
                game_date=game_date,
                season=season,
                home_team_id=home_team.id,
                away_team_id=away_team.id,
                status=status
            )

            self.session.add(game)
            self.session.flush()  # Get the game ID without committing

            logger.debug(f"  Created game: {game_id}")
            return game

        except Exception as e:
            logger.error(f"  Error creating game {game_id}: {e}")
            return None

    def _create_player_game_stats(self, player: Player, game: Game, game_row):
        """Create player game stats record."""
        # Check if stats already exist
        existing = self.session.query(PlayerGameStats).filter_by(
            player_id=player.id,
            game_id=game.id
        ).first()

        if existing:
            return False

        # Create stats record
        stats = PlayerGameStats(
            player_id=player.id,
            game_id=game.id,
            minutes=game_row.get('MIN'),
            points=game_row.get('PTS'),
            field_goals_made=game_row.get('FGM'),
            field_goals_attempted=game_row.get('FGA'),
            three_pointers_made=game_row.get('FG3M'),
            three_pointers_attempted=game_row.get('FG3A'),
            free_throws_made=game_row.get('FTM'),
            free_throws_attempted=game_row.get('FTA'),
            rebounds=game_row.get('REB'),
            offensive_rebounds=game_row.get('OREB'),
            defensive_rebounds=game_row.get('DREB'),
            assists=game_row.get('AST'),
            steals=game_row.get('STL'),
            blocks=game_row.get('BLK'),
            turnovers=game_row.get('TOV'),
            personal_fouls=game_row.get('PF'),
            plus_minus=game_row.get('PLUS_MINUS'),
        )

        self.session.add(stats)
        return True

    def close(self):
        """Close database session."""
        self.session.close()


def main():
    """Main entry point for historical backfill."""
    import argparse

    parser = argparse.ArgumentParser(description='Backfill historical NBA data')
    parser.add_argument(
        '--season',
        default='2024-25',
        help='NBA season (e.g., 2024-25, 2023-24)'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=None,
        help='Limit number of games to process (for testing)'
    )

    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("Historical Data Backfill")
    logger.info("=" * 60)
    logger.info(f"Season: {args.season}")
    if args.limit:
        logger.info(f"Limit: {args.limit} games")
    logger.info("")

    backfill = HistoricalDataBackfill()

    try:
        backfill.backfill_season_games(season=args.season, limit=args.limit)
    except KeyboardInterrupt:
        logger.info("\n\nBackfill interrupted by user")
    except Exception as e:
        logger.error(f"\n\nBackfill failed: {e}")
        raise
    finally:
        backfill.close()


if __name__ == "__main__":
    main()
