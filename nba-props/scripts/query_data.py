#!/usr/bin/env python3
# scripts/query_data.py
"""Simple script to query and inspect collected NBA data."""
import sys
import os
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_session, Team, Player, Game, PropLine, PlayerGameStats, Prediction
from sqlalchemy import func, desc


def show_database_stats():
    """Show overall database statistics."""
    session = get_session()

    print("=" * 60)
    print("DATABASE STATISTICS")
    print("=" * 60)
    print(f"Teams:              {session.query(Team).count()}")
    print(f"Players:            {session.query(Player).count()}")
    print(f"Games:              {session.query(Game).count()}")
    print(f"Player Game Stats:  {session.query(PlayerGameStats).count()}")
    print(f"Prop Lines:         {session.query(PropLine).count()}")
    print(f"Predictions:        {session.query(Prediction).count()}")
    print("")

    session.close()


def show_recent_games(days: int = 7):
    """Show recent games."""
    session = get_session()

    cutoff_date = datetime.now().date() - timedelta(days=days)

    games = session.query(Game).filter(
        Game.game_date >= cutoff_date
    ).order_by(desc(Game.game_date)).limit(20).all()

    print(f"RECENT GAMES (Last {days} days)")
    print("=" * 60)

    for game in games:
        home = session.query(Team).get(game.home_team_id)
        away = session.query(Team).get(game.away_team_id)

        print(f"{game.game_date} | {away.abbreviation} @ {home.abbreviation} | {game.status}")

    print("")
    session.close()


def show_player_props_for_today():
    """Show player props available for today's games."""
    session = get_session()

    today = datetime.now().date()

    games = session.query(Game).filter(
        Game.game_date == today,
        Game.status == 'scheduled'
    ).all()

    print(f"TODAY'S PLAYER PROPS ({today})")
    print("=" * 60)

    if not games:
        print("No games scheduled for today")
        print("")
        session.close()
        return

    for game in games:
        home = session.query(Team).get(game.home_team_id)
        away = session.query(Team).get(game.away_team_id)

        print(f"\n{away.abbreviation} @ {home.abbreviation}")
        print("-" * 60)

        # Get props for this game
        props = session.query(PropLine).filter(
            PropLine.game_id == game.id,
            PropLine.is_latest == True
        ).order_by(PropLine.player_id, PropLine.prop_type).all()

        if not props:
            print("  No props available yet")
            continue

        # Group by player
        current_player_id = None
        for prop in props:
            player = session.query(Player).get(prop.player_id)

            if current_player_id != prop.player_id:
                print(f"\n  {player.full_name}:")
                current_player_id = prop.player_id

            odds_str = ""
            if prop.over_odds:
                odds_str += f"O{prop.over_odds:+d}"
            if prop.under_odds:
                if odds_str:
                    odds_str += " / "
                odds_str += f"U{prop.under_odds:+d}"

            print(f"    {prop.prop_type:15s} {prop.line_value:>5.1f}  ({prop.sportsbook}) [{odds_str}]")

    print("")
    session.close()


def show_player_recent_stats(player_name: str, limit: int = 10):
    """Show recent game stats for a specific player."""
    session = get_session()

    # Find player
    player = session.query(Player).filter(
        Player.full_name.ilike(f"%{player_name}%")
    ).first()

    if not player:
        print(f"Player not found: {player_name}")
        session.close()
        return

    print(f"RECENT STATS: {player.full_name}")
    print("=" * 60)

    # Get recent stats
    stats = session.query(PlayerGameStats).join(Game).filter(
        PlayerGameStats.player_id == player.id
    ).order_by(desc(Game.game_date)).limit(limit).all()

    if not stats:
        print("No stats found")
        session.close()
        return

    print(f"{'Date':<12} {'Opp':<10} {'Min':<5} {'PTS':<4} {'REB':<4} {'AST':<4} {'STL':<4} {'BLK':<4}")
    print("-" * 60)

    for stat in stats:
        game = session.query(Game).get(stat.game_id)

        # Determine opponent
        if player.team_id == game.home_team_id:
            opp_team = session.query(Team).get(game.away_team_id)
            opp_str = f"vs {opp_team.abbreviation}"
        else:
            opp_team = session.query(Team).get(game.home_team_id)
            opp_str = f"@ {opp_team.abbreviation}"

        print(f"{str(game.game_date):<12} {opp_str:<10} {stat.minutes or 0:<5.1f} "
              f"{stat.points or 0:<4} {stat.rebounds or 0:<4} {stat.assists or 0:<4} "
              f"{stat.steals or 0:<4} {stat.blocks or 0:<4}")

    # Calculate averages
    total_games = len(stats)
    avg_pts = sum(s.points or 0 for s in stats) / total_games
    avg_reb = sum(s.rebounds or 0 for s in stats) / total_games
    avg_ast = sum(s.assists or 0 for s in stats) / total_games

    print("-" * 60)
    print(f"{'Averages:':<23} {avg_pts:>4.1f} {avg_reb:>4.1f} {avg_ast:>4.1f}")
    print("")

    session.close()


def show_top_players_by_stat(stat: str = 'points', limit: int = 10):
    """Show top players by a specific stat (season average)."""
    session = get_session()

    stat_map = {
        'points': PlayerGameStats.points,
        'rebounds': PlayerGameStats.rebounds,
        'assists': PlayerGameStats.assists,
        'steals': PlayerGameStats.steals,
        'blocks': PlayerGameStats.blocks,
    }

    if stat not in stat_map:
        print(f"Invalid stat. Choose from: {', '.join(stat_map.keys())}")
        session.close()
        return

    stat_column = stat_map[stat]

    # Calculate averages
    results = session.query(
        Player,
        func.avg(stat_column).label('avg'),
        func.count(PlayerGameStats.id).label('games')
    ).join(PlayerGameStats).group_by(Player.id).having(
        func.count(PlayerGameStats.id) >= 5  # At least 5 games
    ).order_by(desc('avg')).limit(limit).all()

    print(f"TOP {limit} PLAYERS - {stat.upper()} (Season Average)")
    print("=" * 60)
    print(f"{'Player':<25} {'Team':<5} {'Avg':<6} {'Games':<6}")
    print("-" * 60)

    for player, avg, games in results:
        team = session.query(Team).get(player.team_id) if player.team_id else None
        team_abbr = team.abbreviation if team else "N/A"

        print(f"{player.full_name:<25} {team_abbr:<5} {avg:>5.1f} {games:>6}")

    print("")
    session.close()


def interactive_menu():
    """Interactive menu for querying data."""
    while True:
        print("\n" + "=" * 60)
        print("NBA PROPS DATA QUERY TOOL")
        print("=" * 60)
        print("1. Database Statistics")
        print("2. Recent Games")
        print("3. Today's Player Props")
        print("4. Player Recent Stats")
        print("5. Top Players by Stat")
        print("0. Exit")
        print("")

        choice = input("Select option: ").strip()

        if choice == "1":
            show_database_stats()
        elif choice == "2":
            show_recent_games()
        elif choice == "3":
            show_player_props_for_today()
        elif choice == "4":
            player_name = input("Enter player name: ").strip()
            show_player_recent_stats(player_name)
        elif choice == "5":
            stat = input("Enter stat (points/rebounds/assists/steals/blocks): ").strip().lower()
            show_top_players_by_stat(stat)
        elif choice == "0":
            print("Goodbye!")
            break
        else:
            print("Invalid option")

        input("\nPress Enter to continue...")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()

        if command == "stats":
            show_database_stats()
        elif command == "games":
            show_recent_games()
        elif command == "props":
            show_player_props_for_today()
        elif command == "player" and len(sys.argv) > 2:
            player_name = " ".join(sys.argv[2:])
            show_player_recent_stats(player_name)
        elif command == "top" and len(sys.argv) > 2:
            stat = sys.argv[2]
            show_top_players_by_stat(stat)
        else:
            print("Usage:")
            print("  python query_data.py stats              - Show database statistics")
            print("  python query_data.py games              - Show recent games")
            print("  python query_data.py props              - Show today's props")
            print("  python query_data.py player <name>      - Show player stats")
            print("  python query_data.py top <stat>         - Show top players")
            print("  python query_data.py                    - Interactive mode")
    else:
        interactive_menu()
