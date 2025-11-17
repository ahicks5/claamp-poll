#!/usr/bin/env python3
# scripts/backfill_historical_odds.py
"""Backfill historical prop odds from The Odds API for completed games."""
import sys
import os
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional

# Add parent directory to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# Load environment variables early
from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, '.env'))
load_dotenv(os.path.join(os.path.dirname(PROJECT_ROOT), '.env'))

from database import get_session, Game, Player, Team, PropLine
from services.odds_api_client import OddsAPIClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class HistoricalOddsBackfiller:
    """Backfill historical prop odds from The Odds API."""

    def __init__(self, api_key: str):
        self.session = get_session()
        self.odds_client = OddsAPIClient(api_key)
        self.api_requests_made = 0
        self.props_added = 0

    def backfill_season(
        self,
        season: str = "2025-26",
        limit: Optional[int] = None,
        delay_between_games: float = 1.0
    ):
        """
        Backfill historical odds for all completed games in a season.

        Args:
            season: Season in format "2025-26"
            limit: Limit number of games to process (for testing)
            delay_between_games: Seconds to wait between game requests
        """
        logger.info("="*60)
        logger.info(f"BACKFILLING HISTORICAL ODDS - Season {season}")
        logger.info("="*60)

        # Get all completed games for the season
        games = self._get_completed_games(season, limit)

        if not games:
            logger.warning(f"No completed games found for season {season}")
            return

        logger.info(f"Found {len(games)} completed games to backfill")

        # Process each game
        for i, game in enumerate(games, 1):
            logger.info(f"\n[{i}/{len(games)}] Processing game: {game.home_team.name} vs {game.away_team.name} on {game.game_date}")

            # Check if we already have odds for this game
            existing_props = self.session.query(PropLine).filter(
                PropLine.game_id == game.id
            ).count()

            if existing_props > 0:
                logger.info(f"  Already have {existing_props} props for this game, skipping...")
                continue

            # Fetch historical odds for this game
            try:
                self._fetch_game_odds(game)
                time.sleep(delay_between_games)  # Rate limiting
            except Exception as e:
                logger.error(f"  Error fetching odds for game {game.id}: {e}")
                continue

        # Summary
        logger.info("\n" + "="*60)
        logger.info("BACKFILL COMPLETE")
        logger.info("="*60)
        logger.info(f"Games processed: {len(games)}")
        logger.info(f"Props added: {self.props_added}")
        logger.info(f"API requests made: {self.api_requests_made}")
        logger.info(f"\nEstimated API credits used: ~{self.api_requests_made}")

    def _get_completed_games(self, season: str, limit: Optional[int] = None) -> List[Game]:
        """Get all completed games for a season."""
        # Parse season string (e.g., "2025-26" -> start year 2025)
        start_year = int(season.split('-')[0])

        # NBA season starts in October and ends in June
        season_start = datetime(start_year, 10, 1).date()
        season_end = datetime(start_year + 1, 6, 30).date()

        query = self.session.query(Game).filter(
            Game.game_date >= season_start,
            Game.game_date <= season_end,
            Game.status == 'final'
        ).order_by(Game.game_date.asc())

        if limit:
            query = query.limit(limit)

        return query.all()

    def _fetch_game_odds(self, game: Game):
        """Fetch historical odds for a specific game."""
        # The Odds API uses team abbreviations
        home_team_abbr = self._get_team_abbreviation(game.home_team)
        away_team_abbr = self._get_team_abbreviation(game.away_team)

        # Request odds from a few hours before game time
        # (odds are typically set 12-24 hours before game)
        game_datetime = datetime.combine(game.game_date, datetime.min.time())
        fetch_time = game_datetime - timedelta(hours=2)

        logger.info(f"  Fetching odds from around {fetch_time.strftime('%Y-%m-%d %H:%M')}")

        # Fetch player props for this game
        # The Odds API groups by market type
        prop_types_to_fetch = [
            'player_points',
            'player_rebounds',
            'player_assists',
            'player_threes',
            'player_blocks',
            'player_steals',
            'player_turnovers'
        ]

        for market in prop_types_to_fetch:
            try:
                props = self._fetch_historical_market(
                    game_date=game.game_date,
                    market=market,
                    home_team=home_team_abbr,
                    away_team=away_team_abbr
                )

                if props:
                    self._store_props(game, props, market)
                    logger.info(f"    Added {len(props)} {market} props")

                time.sleep(0.5)  # Small delay between market requests

            except Exception as e:
                logger.error(f"    Error fetching {market}: {e}")
                continue

    def _fetch_historical_market(
        self,
        game_date: datetime.date,
        market: str,
        home_team: str,
        away_team: str
    ) -> List[Dict]:
        """
        Fetch historical odds for a specific market.

        NOTE: The Odds API historical endpoint requires a date parameter.
        Format: ISO 8601 (e.g., "2025-10-22T12:00:00Z")

        IMPORTANT: Historical data may only be available for recent games (30-90 days).
        """
        # Convert game date to ISO 8601 format
        # Fetch odds from noon on game day (when lines are typically set)
        fetch_datetime = datetime.combine(game_date, datetime.min.time())
        fetch_datetime = fetch_datetime.replace(hour=12, tzinfo=timezone.utc)
        date_str = fetch_datetime.isoformat()

        try:
            # Make API request
            response = self.odds_client._make_request(
                endpoint='historical/sports/basketball_nba/odds',
                params={
                    'regions': 'us',
                    'markets': market,
                    'date': date_str,
                    'oddsFormat': 'american'
                }
            )

            self.api_requests_made += 1

            if not response:
                logger.warning(f"    No response from API for {market}")
                return []

            # The historical API returns data in 'data' field
            events_data = response.get('data', response) if isinstance(response, dict) else response

            # Handle if response is a list directly
            if isinstance(events_data, list):
                events = events_data
            elif isinstance(events_data, dict):
                events = [events_data]
            else:
                logger.warning(f"    Unexpected response format for {market}")
                return []

            # Filter for games involving our teams
            game_data = None
            for event in events:
                event_home = event.get('home_team', '')
                event_away = event.get('away_team', '')

                # Match by team abbreviation or full name
                if (home_team.upper() in event_home.upper() and away_team.upper() in event_away.upper()) or \
                   (away_team.upper() in event_home.upper() and home_team.upper() in event_away.upper()):
                    game_data = event
                    break

            if not game_data:
                logger.debug(f"    No matching game found for {home_team} vs {away_team}")
                return []

            # Extract player props from bookmakers
            props = []
            bookmakers = game_data.get('bookmakers', [])

            if not bookmakers:
                logger.debug(f"    No bookmakers data for {market}")
                return []

            for bookmaker in bookmakers:
                sportsbook = bookmaker.get('key', 'unknown')

                for market_data in bookmaker.get('markets', []):
                    if market_data.get('key') != market:
                        continue

                    for outcome in market_data.get('outcomes', []):
                        player_name = outcome.get('description', '')
                        line_value = outcome.get('point')
                        outcome_name = outcome.get('name', '')
                        odds = outcome.get('price')

                        if not player_name or line_value is None:
                            continue

                        # Group over/under for same player/line
                        props.append({
                            'player_name': player_name,
                            'line_value': float(line_value),
                            'over_odds': odds if 'over' in outcome_name.lower() else None,
                            'under_odds': odds if 'under' in outcome_name.lower() else None,
                            'sportsbook': sportsbook,
                            'market': market
                        })

            return props

        except Exception as e:
            logger.error(f"    API request failed for {market}: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return []

    def _store_props(self, game: Game, props: List[Dict], market: str):
        """Store fetched props in database."""
        # Map market name to prop_type
        market_to_prop_type = {
            'player_points': 'points',
            'player_rebounds': 'rebounds',
            'player_assists': 'assists',
            'player_threes': 'threes',
            'player_blocks': 'blocks',
            'player_steals': 'steals',
            'player_turnovers': 'turnovers'
        }

        prop_type = market_to_prop_type.get(market, market)

        for prop_data in props:
            player_name = prop_data.get('player_name', '')
            if not player_name:
                continue

            # Find player in database
            player = self.session.query(Player).filter(
                Player.full_name.ilike(f"%{player_name}%")
            ).first()

            if not player:
                # Try matching by last name only
                last_name = player_name.split()[-1] if ' ' in player_name else player_name
                player = self.session.query(Player).filter(
                    Player.full_name.ilike(f"%{last_name}%")
                ).first()

            if not player:
                logger.debug(f"    Player not found: {player_name}")
                continue

            # Create PropLine record
            prop_line = PropLine(
                player_id=player.id,
                game_id=game.id,
                prop_type=prop_type,
                line_value=prop_data.get('line_value'),
                over_odds=prop_data.get('over_odds'),
                under_odds=prop_data.get('under_odds'),
                sportsbook=prop_data.get('sportsbook', 'unknown'),
                fetched_at=datetime.now(timezone.utc),
                is_latest=False  # Historical data, not current
            )

            self.session.add(prop_line)
            self.props_added += 1

        # Commit after each game
        try:
            self.session.commit()
        except Exception as e:
            logger.error(f"    Error saving props: {e}")
            self.session.rollback()

    def _get_team_abbreviation(self, team: Team) -> str:
        """Get team abbreviation for Odds API."""
        # The Odds API uses specific team identifiers
        # Map our team names to their abbreviations
        abbrev_map = {
            'Atlanta Hawks': 'ATL',
            'Boston Celtics': 'BOS',
            'Brooklyn Nets': 'BKN',
            'Charlotte Hornets': 'CHA',
            'Chicago Bulls': 'CHI',
            'Cleveland Cavaliers': 'CLE',
            'Dallas Mavericks': 'DAL',
            'Denver Nuggets': 'DEN',
            'Detroit Pistons': 'DET',
            'Golden State Warriors': 'GSW',
            'Houston Rockets': 'HOU',
            'Indiana Pacers': 'IND',
            'LA Clippers': 'LAC',
            'Los Angeles Lakers': 'LAL',
            'Memphis Grizzlies': 'MEM',
            'Miami Heat': 'MIA',
            'Milwaukee Bucks': 'MIL',
            'Minnesota Timberwolves': 'MIN',
            'New Orleans Pelicans': 'NOP',
            'New York Knicks': 'NYK',
            'Oklahoma City Thunder': 'OKC',
            'Orlando Magic': 'ORL',
            'Philadelphia 76ers': 'PHI',
            'Phoenix Suns': 'PHX',
            'Portland Trail Blazers': 'POR',
            'Sacramento Kings': 'SAC',
            'San Antonio Spurs': 'SAS',
            'Toronto Raptors': 'TOR',
            'Utah Jazz': 'UTA',
            'Washington Wizards': 'WAS'
        }

        return abbrev_map.get(team.name, team.abbreviation or 'UNK')

    def close(self):
        """Close database session."""
        self.session.close()


def main():
    """Main backfill script."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Backfill historical prop odds from The Odds API'
    )
    parser.add_argument(
        '--season',
        default='2025-26',
        help='Season to backfill (e.g., 2025-26)'
    )
    parser.add_argument(
        '--limit',
        type=int,
        help='Limit number of games to process (for testing)'
    )
    parser.add_argument(
        '--delay',
        type=float,
        default=1.0,
        help='Seconds to wait between game requests (default: 1.0)'
    )

    args = parser.parse_args()

    # Get API key
    api_key = os.getenv('ODDS_API_KEY')
    if not api_key:
        logger.error("ODDS_API_KEY not found in environment")
        logger.error("Add it to your .env file")
        return

    logger.info(f"Season: {args.season}")
    if args.limit:
        logger.info(f"Limit: {args.limit} games (test mode)")
    logger.info("")

    backfiller = HistoricalOddsBackfiller(api_key)

    try:
        backfiller.backfill_season(
            season=args.season,
            limit=args.limit,
            delay_between_games=args.delay
        )

        logger.info("\n[OK] Historical odds backfill complete!")
        logger.info("\nNext steps:")
        logger.info("  1. Train full model: python scripts/train_model.py --prop-type points")
        logger.info("  2. Generate predictions: python scripts/generate_predictions.py")

    except KeyboardInterrupt:
        logger.info("\n\nBackfill interrupted by user")
        logger.info(f"Progress: {backfiller.props_added} props added")
    except Exception as e:
        logger.error(f"\nBackfill failed: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        backfiller.close()


if __name__ == "__main__":
    main()
