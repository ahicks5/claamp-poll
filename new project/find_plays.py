"""
Find Today's Best Plays

Analyze all props and show the ones with biggest deviations
"""
from database.db import get_session
from database.models import PropLine, Player, Game, Team
from analyzer import PropAnalyzer
from tabulate import tabulate


def find_plays(min_z_score: float = 0.5, max_plays: int = 20):
    """
    Find best plays based on deviation from expected

    Args:
        min_z_score: Minimum absolute z-score to consider
        max_plays: Maximum plays to show
    """
    print("\n" + "="*90)
    print("  🏀 DAILY PICKS - Following Vegas Deviations")
    print("="*90)

    analyzer = PropAnalyzer()
    db = get_session()

    try:
        # Get all latest props
        props = db.query(PropLine).filter(PropLine.is_latest == True).all()

        if not props:
            print("\n⚠️  No props found in database")
            print("   Run collect_today.py first!")
            return

        print(f"\nAnalyzing {len(props)} props...")

        plays = []

        for prop_line in props:
            player = db.query(Player).get(prop_line.player_id)
            if not player:
                continue

            # For now, use "UNK" as opponent
            # In full version, would get actual opponent from game
            opponent_abbr = "UNK"

            # Analyze
            analysis = analyzer.analyze_prop(
                player_id=player.nba_player_id,
                player_name=player.full_name,
                stat_type=prop_line.prop_type,
                line_value=prop_line.line_value,
                opponent_abbr=opponent_abbr
            )

            if analysis and abs(analysis['z_score']) >= min_z_score:
                plays.append(analysis)

        # Sort by z-score
        plays.sort(key=lambda x: abs(x['z_score']), reverse=True)

        # Display
        if not plays:
            print("\n⚠️  No significant deviations found")
            print(f"   (Looking for |z-score| >= {min_z_score})")
        else:
            print(f"\n✅ Found {len(plays)} plays with significant deviations\n")
            display_plays(plays[:max_plays])

    finally:
        db.close()


def display_plays(plays):
    """Display plays in table format"""
    table_data = []

    for play in plays:
        table_data.append([
            play['player_name'][:20],
            play['stat_type'][:3].upper(),
            f"{play['line_value']:.1f}",
            f"{play['season_avg']:.1f}",
            f"{play['recent_avg']:.1f}",
            f"{play['expected']:.1f}",
            f"{play['deviation']:+.1f}",
            f"{play['z_score']:+.2f}",
            play['recommendation'],
            play['confidence']
        ])

    headers = ['Player', 'Stat', 'Line', 'Szn', 'L5', 'Exp', 'Dev', 'Z', 'Pick', 'Conf']

    print(tabulate(table_data, headers=headers, tablefmt='simple'))

    # Show reasoning for top 3
    print("\n📋 Top 3 Plays:")
    print("-" * 90)

    for i, play in enumerate(plays[:3], 1):
        print(f"\n{i}. {play['player_name']} - {play['stat_type'].upper()} O/U {play['line_value']}")
        print(f"   {play['reasoning']}")

    print("\n" + "="*90)


if __name__ == "__main__":
    import sys

    # Allow custom z-score threshold
    min_z = float(sys.argv[1]) if len(sys.argv) > 1 else 0.5

    find_plays(min_z_score=min_z, max_plays=20)
