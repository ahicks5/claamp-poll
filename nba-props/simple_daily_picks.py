"""
Simple Daily Picks Finder
Uses basic stats to find props where Vegas line is WAY OFF from expected

Run this daily to find plays where "Vegas knows something"
"""
import sys
from datetime import date
from tabulate import tabulate

sys.path.insert(0, '/home/user/claamp-poll/nba-props')

from simple_analyzer import SimplePropsAnalyzer


def find_todays_picks(min_z_score: float = 0.75, max_plays: int = 20):
    """
    Find today's best plays based on deviation from expected

    Args:
        min_z_score: Minimum deviation (0.75 = 3/4 std dev, 1.0 = 1 full std dev)
        max_plays: Maximum plays to show

    Strategy:
        - If line is LOWER than expected → Vegas thinks underperformance → Bet UNDER
        - If line is HIGHER than expected → Vegas thinks overperformance → Bet OVER
        - Bigger deviation = stronger signal that Vegas knows something
    """
    print("\n" + "="*90)
    print("  🏀 DAILY PICKS - Following Vegas Deviations")
    print("="*90)

    analyzer = SimplePropsAnalyzer()

    # For testing, let's manually analyze some props
    # In production, this would pull from today's prop lines in database

    print("\nStrategy: Find props where Vegas line is WAY OFF from player's expected stats")
    print("Theory: Big deviation = Vegas has inside info (injuries, matchups, rest, etc.)\n")

    # Example players to test (in real version, would loop through all props)
    test_cases = [
        {
            'player_id': 2544,
            'player_name': 'LeBron James',
            'stat_type': 'points',
            'line_value': 20.5,  # Line lower than his avg (24.4)
            'opponent': 'BOS'
        },
        {
            'player_id': 2544,
            'player_name': 'LeBron James',
            'stat_type': 'points',
            'line_value': 27.5,  # Line higher than his avg (24.4)
            'opponent': 'BOS'
        },
        {
            'player_id': 201939,
            'player_name': 'Stephen Curry',
            'stat_type': 'points',
            'line_value': 25.5,
            'opponent': 'LAL'
        },
        {
            'player_id': 2544,
            'player_name': 'LeBron James',
            'stat_type': 'assists',
            'line_value': 6.5,
            'opponent': 'BOS'
        }
    ]

    plays = []

    for case in test_cases:
        analysis = analyzer.analyze_prop_line(
            player_id=case['player_id'],
            player_name=case['player_name'],
            stat_type=case['stat_type'],
            line_value=case['line_value'],
            opponent_team_abbr=case['opponent']
        )

        if analysis:
            plays.append(analysis)

    # Filter by z-score
    significant_plays = [p for p in plays if abs(p['z_score']) >= min_z_score]

    if not significant_plays:
        print("⚠️  No significant deviations found today")
        print(f"   (Looking for |z-score| >= {min_z_score})")
        print("\nAll analyzed props:")
        _display_plays(plays)
    else:
        # Sort by absolute z-score (biggest deviations first)
        significant_plays.sort(key=lambda x: abs(x['z_score']), reverse=True)

        print(f"✅ Found {len(significant_plays)} plays with significant deviations:\n")
        _display_plays(significant_plays[:max_plays])

    print("\n" + "="*90)
    print("  💡 Interpretation Guide")
    print("="*90)
    print("""
Z-Score Meaning:
  < 0.5  : No edge, line is fair
  0.5-1.0: Moderate deviation, possible edge
  > 1.0  : Strong deviation, Vegas likely has inside info

Recommendation Logic:
  Line < Expected → UNDER (Vegas thinks they'll underperform)
  Line > Expected → OVER (Vegas thinks they'll overperform)

Example:
  LeBron averages 24 points, line is 20.5 → UNDER (Vegas knows something)
  LeBron averages 24 points, line is 28.5 → OVER (Vegas knows something)
""")

    analyzer.close()


def _display_plays(plays):
    """Display plays in a nice table"""
    if not plays:
        print("No plays to display")
        return

    table_data = []
    for play in plays:
        table_data.append([
            play['player_name'][:20],
            play['stat_type'].upper()[:3],
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

    # Show reasoning for top 3 plays
    print("\n📋 Detailed Reasoning (Top 3):")
    print("-" * 90)

    for i, play in enumerate(plays[:3], 1):
        print(f"\n{i}. {play['player_name']} - {play['stat_type'].upper()} O/U {play['line_value']}")
        print(f"   {play['reasoning']}")


if __name__ == "__main__":
    # Run the picker
    find_todays_picks(min_z_score=0.5, max_plays=20)
