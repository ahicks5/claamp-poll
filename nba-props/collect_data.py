#!/usr/bin/env python3
"""
Collect Today's Games and Props
Simple workflow - no ML model needed
"""
import sys
from datetime import date, datetime, timezone
import logging

sys.path.insert(0, '/home/user/claamp-poll/nba-props')

from database.db import SessionLocal
from database.models import Game, Team, Player, PropLine
from services.nba_api_client import NBAAPIClient
from services.odds_api_client import OddsAPIClient

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def collect_todays_games():
    """
    Collect today's NBA games and store in database
    """
    logger.info("=" * 70)
    logger.info("STEP 1: Collecting Today's NBA Games")
    logger.info("=" * 70)

    nba_client = NBAAPIClient()
    db = SessionLocal()

    try:
        today = date.today()
        logger.info(f"Fetching games for {today}...")

        # Get today's games from NBA API
        games_data = nba_client.get_games_for_date(today)
        logger.info(f"Found {len(games_data)} games")

        if len(games_data) == 0:
            logger.warning("No games today. This might be off-season or off-day.")
            return 0

        games_stored = 0

        for game_data in games_data:
            # Check if game already exists
            existing = db.query(Game).filter(
                Game.nba_game_id == game_data['game_id']
            ).first()

            if existing:
                logger.debug(f"Game already exists: {game_data['game_id']}")
                continue

            # Create new game record
            game = Game(
                nba_game_id=game_data['game_id'],
                game_date=game_data['game_date'],
                season=game_data.get('season', '2024-25'),
                home_team_id=game_data.get('home_team_id'),
                away_team_id=game_data.get('away_team_id'),
                status=game_data.get('status', 'scheduled')
            )

            db.add(game)
            games_stored += 1

            # Log the matchup
            home_team = db.query(Team).get(game_data.get('home_team_id'))
            away_team = db.query(Team).get(game_data.get('away_team_id'))

            if home_team and away_team:
                logger.info(f"  ✓ {away_team.abbreviation} @ {home_team.abbreviation}")

        db.commit()
        logger.info(f"\n✅ Stored {games_stored} new games\n")

        return games_stored

    except Exception as e:
        logger.error(f"Error collecting games: {e}")
        db.rollback()
        return 0
    finally:
        db.close()


def collect_todays_props():
    """
    Collect today's prop lines from Odds API
    """
    logger.info("=" * 70)
    logger.info("STEP 2: Collecting Today's Prop Lines from Odds API")
    logger.info("=" * 70)

    odds_client = OddsAPIClient()
    db = SessionLocal()

    try:
        # Get upcoming games from Odds API
        logger.info("Fetching upcoming NBA games from Odds API...")
        upcoming_games = odds_client.get_upcoming_games(days_ahead=1)

        if not upcoming_games:
            logger.warning("No upcoming games found in Odds API")
            return 0

        logger.info(f"Found {len(upcoming_games)} games with odds available\n")

        total_props = 0

        for odds_game in upcoming_games:
            game_id = odds_game.get('id')
            home_team = odds_game.get('home_team')
            away_team = odds_game.get('away_team')

            logger.info(f"Fetching props for: {away_team} @ {home_team}")

            # Get player props for this game
            props_data = odds_client.get_player_props(event_id=game_id)

            if not props_data:
                logger.warning(f"  No props available yet")
                continue

            # Parse and store props
            bookmakers = props_data.get('bookmakers', [])

            if not bookmakers:
                logger.warning(f"  No bookmakers offering props")
                continue

            # Use first bookmaker (usually DraftKings or FanDuel)
            bookmaker = bookmakers[0]
            bookmaker_name = bookmaker.get('title', 'Unknown')

            logger.info(f"  Using {bookmaker_name}")

            markets = bookmaker.get('markets', [])

            for market in markets:
                market_key = market.get('key')  # e.g., 'player_points'

                # Map market key to our prop_type
                prop_type_map = {
                    'player_points': 'points',
                    'player_rebounds': 'rebounds',
                    'player_assists': 'assists',
                    'player_threes': 'threes',
                    'player_steals': 'steals',
                    'player_blocks': 'blocks'
                }

                prop_type = prop_type_map.get(market_key)
                if not prop_type:
                    continue  # Skip unknown market types

                outcomes = market.get('outcomes', [])

                for outcome in outcomes:
                    player_name = outcome.get('description')
                    line_value = outcome.get('point')
                    over_odds = outcome.get('price') if outcome.get('name') == 'Over' else None
                    under_odds = outcome.get('price') if outcome.get('name') == 'Under' else None

                    if not player_name or line_value is None:
                        continue

                    # Find player in database
                    player = db.query(Player).filter(
                        Player.full_name.like(f"%{player_name}%")
                    ).first()

                    if not player:
                        logger.debug(f"    Player not found: {player_name}")
                        continue

                    # Find game in database
                    # Match by teams (simplified)
                    game = db.query(Game).join(Team, Team.id == Game.home_team_id).filter(
                        Team.abbreviation == home_team
                    ).filter(
                        Game.game_date == date.today()
                    ).first()

                    if not game:
                        logger.debug(f"    Game not found in database")
                        continue

                    # Mark old props as not latest
                    db.query(PropLine).filter(
                        PropLine.player_id == player.id,
                        PropLine.game_id == game.id,
                        PropLine.prop_type == prop_type
                    ).update({'is_latest': False})

                    # Create new prop line
                    prop_line = PropLine(
                        player_id=player.id,
                        game_id=game.id,
                        prop_type=prop_type,
                        line_value=line_value,
                        over_odds=over_odds,
                        under_odds=under_odds,
                        sportsbook=bookmaker_name,
                        market_key=market_key,
                        is_latest=True,
                        fetched_at=datetime.now(timezone.utc)
                    )

                    db.add(prop_line)
                    total_props += 1

                    logger.debug(f"    ✓ {player_name} {prop_type} O/U {line_value}")

            db.commit()
            logger.info(f"  Stored props for this game")

        logger.info(f"\n✅ Stored {total_props} total prop lines\n")

        return total_props

    except Exception as e:
        logger.error(f"Error collecting props: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
        return 0
    finally:
        db.close()


def verify_data():
    """
    Verify what data we have in the database
    """
    logger.info("=" * 70)
    logger.info("STEP 3: Verifying Data in Database")
    logger.info("=" * 70)

    db = SessionLocal()

    try:
        today = date.today()

        games_count = db.query(Game).filter(Game.game_date == today).count()
        props_count = db.query(PropLine).filter(PropLine.is_latest == True).count()

        logger.info(f"\nData collected for {today}:")
        logger.info(f"  Games: {games_count}")
        logger.info(f"  Prop Lines: {props_count}")

        if games_count > 0 and props_count > 0:
            # Show sample props
            logger.info(f"\nSample props:")

            sample_props = (
                db.query(PropLine)
                .filter(PropLine.is_latest == True)
                .limit(5)
                .all()
            )

            for prop in sample_props:
                player = db.query(Player).get(prop.player_id)
                game = db.query(Game).get(prop.game_id)

                if player and game:
                    logger.info(f"  {player.full_name} - {prop.prop_type} O/U {prop.line_value}")

            logger.info(f"\n✅ Ready to run simple_daily_picks.py with real data!")
        else:
            logger.warning("\n⚠️  No data collected. Check errors above.")

    finally:
        db.close()


def main():
    """
    Main workflow: Collect games and props
    """
    print("\n" + "="*70)
    print("  📊 COLLECT TODAY'S GAMES & PROPS")
    print("="*70 + "\n")

    # Step 1: Collect games
    games = collect_todays_games()

    # Step 2: Collect props
    props = collect_todays_props()

    # Step 3: Verify
    verify_data()

    print("\n" + "="*70)
    print("  ✅ DATA COLLECTION COMPLETE")
    print("="*70)

    if games > 0 and props > 0:
        print(f"""
Next step: Run the analyzer!

    cd /home/user/claamp-poll/nba-props
    python simple_daily_picks.py

This will analyze all {props} props and find the best plays.
""")
    else:
        print("\n⚠️  No data collected. Possible reasons:")
        print("  - No games scheduled today")
        print("  - Odds API not returning props yet (props usually available ~24hrs before)")
        print("  - Check your ODDS_API_KEY in .env")

    print("="*70 + "\n")


if __name__ == "__main__":
    main()
