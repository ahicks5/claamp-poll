"""
Collect Today's Data

1. Fetch today's NBA games
2. Fetch prop lines from Odds API
3. Store in database
"""
import os
from datetime import date, datetime, timezone
from database.db import get_session, init_database
from database.models import Team, Player, Game, PropLine
from services.nba_api import NBAAPIClient
from services.odds_api import OddsAPIClient


def init_teams_and_players():
    """Initialize teams and players (run once)"""
    print("Initializing teams and players...")

    nba_client = NBAAPIClient()
    db = get_session()

    try:
        # Load teams
        teams_data = nba_client.get_all_teams()
        for team_data in teams_data:
            existing = db.query(Team).filter(Team.nba_team_id == team_data['id']).first()
            if not existing:
                team = Team(
                    nba_team_id=team_data['id'],
                    name=team_data['full_name'],
                    abbreviation=team_data['abbreviation'],
                    city=team_data['city']
                )
                db.add(team)

        db.commit()
        print(f"✓ Teams loaded: {db.query(Team).count()}")

        # Load players
        players_data = nba_client.get_all_players()
        for _, player_data in players_data.iterrows():
            existing = db.query(Player).filter(Player.nba_player_id == player_data['PERSON_ID']).first()
            if not existing:
                player = Player(
                    nba_player_id=player_data['PERSON_ID'],
                    full_name=player_data['DISPLAY_FIRST_LAST'],
                    is_active=True
                )
                db.add(player)

        db.commit()
        print(f"✓ Players loaded: {db.query(Player).count()}")

    finally:
        db.close()


def collect_todays_games():
    """Collect today's games"""
    print("\nCollecting today's games...")

    nba_client = NBAAPIClient()
    db = get_session()

    try:
        today = date.today()
        games = nba_client.get_games_for_date(today)

        for game_data in games:
            existing = db.query(Game).filter(Game.nba_game_id == game_data['game_id']).first()
            if not existing:
                game = Game(
                    nba_game_id=game_data['game_id'],
                    game_date=game_data['game_date'],
                    season="2024-25",
                    home_team_id=game_data['home_team_id'],
                    away_team_id=game_data['away_team_id'],
                    status=game_data.get('status', 'scheduled')
                )
                db.add(game)

        db.commit()
        print(f"✓ Games collected: {len(games)}")

        return len(games)

    finally:
        db.close()


def collect_todays_props():
    """Collect today's prop lines"""
    print("\nCollecting today's props...")

    odds_client = OddsAPIClient()
    db = get_session()

    try:
        upcoming_games = odds_client.get_upcoming_games(days_ahead=1)

        if not upcoming_games:
            print("⚠️  No upcoming games found")
            return 0

        total_props = 0

        for odds_game in upcoming_games:
            game_id = odds_game.get('id')
            home_team = odds_game.get('home_team')
            away_team = odds_game.get('away_team')

            print(f"  Fetching props for: {away_team} @ {home_team}")

            # Get props
            props_data = odds_client.get_player_props(event_id=game_id)

            if not props_data or not props_data.get('bookmakers'):
                print(f"    No props available yet")
                continue

            # Use first bookmaker
            bookmaker = props_data['bookmakers'][0]
            bookmaker_name = bookmaker.get('title', 'Unknown')

            for market in bookmaker.get('markets', []):
                market_key = market.get('key')

                # Map to prop type
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
                    continue

                for outcome in market.get('outcomes', []):
                    player_name = outcome.get('description')
                    line_value = outcome.get('point')

                    if not player_name or line_value is None:
                        continue

                    # Find player
                    player = db.query(Player).filter(
                        Player.full_name.like(f"%{player_name}%")
                    ).first()

                    if not player:
                        continue

                    # Mark old props as not latest
                    db.query(PropLine).filter(
                        PropLine.player_id == player.id,
                        PropLine.prop_type == prop_type
                    ).update({'is_latest': False})

                    # Create new prop
                    prop_line = PropLine(
                        player_id=player.id,
                        game_id=1,  # Simplified - would need to match game properly
                        prop_type=prop_type,
                        line_value=line_value,
                        over_odds=outcome.get('price') if outcome.get('name') == 'Over' else None,
                        under_odds=outcome.get('price') if outcome.get('name') == 'Under' else None,
                        sportsbook=bookmaker_name,
                        is_latest=True,
                        fetched_at=datetime.now(timezone.utc)
                    )

                    db.add(prop_line)
                    total_props += 1

            db.commit()

        print(f"✓ Props collected: {total_props}")
        return total_props

    finally:
        db.close()


def main():
    """Main workflow"""
    print("="*70)
    print("  COLLECT TODAY'S DATA")
    print("="*70)

    # Initialize database if needed
    if not os.path.exists("props.db"):
        print("\nInitializing database...")
        init_database()
        init_teams_and_players()

    # Collect data
    games = collect_todays_games()
    props = collect_todays_props()

    print("\n" + "="*70)
    print(f"✅ COMPLETE: {games} games, {props} props")
    print("="*70)

    if props > 0:
        print("\nNext: Run find_plays.py to analyze!")


if __name__ == "__main__":
    # Make sure ODDS_API_KEY is set
    if not os.getenv("ODDS_API_KEY"):
        print("⚠️  Set ODDS_API_KEY in .env file first!")
    else:
        main()
