# Simple Stats-Based Prop Analysis

**No machine learning. Just simple statistics.**

## The Strategy

Find props where Vegas line is **WAY OFF** from what the stats suggest.

**Theory:** When the line deviates significantly from expected → Vegas knows something (injuries, rest, matchups, insider info) → Follow the deviation.

---

## How It Works

### 1. Calculate Expected Value

For each prop, calculate what we'd expect based on:
- **40%** Player's season average
- **40%** Player's last 5 games average
- **20%** Opponent defense (how much they allow)

**Example:**
```
LeBron James - Points
- Season avg: 24.4 PPG
- Last 5 games: 23.0 PPG
- Opponent allows: 25.0 PPG

Expected = (24.4 × 0.4) + (23.0 × 0.4) + (25.0 × 0.2) = 24.0
```

### 2. Compare to Vegas Line

**If line is 20.5:**
- Deviation = 20.5 - 24.0 = **-3.5**
- Z-score = -3.5 / std_dev
- **Vegas set line LOW** → They think he'll underperform → Bet **UNDER**

**If line is 28.5:**
- Deviation = 28.5 - 24.0 = **+4.5**
- Z-score = +4.5 / std_dev
- **Vegas set line HIGH** → They think he'll overperform → Bet **OVER**

### 3. Find Biggest Deviations

- **Z-score < 0.5**: No edge, skip
- **Z-score 0.5-1.0**: Moderate edge, consider
- **Z-score > 1.0**: Strong edge, play it!

---

## Files

### `simple_analyzer.py`
Core analysis engine. Main class: `SimplePropsAnalyzer`

**Key Methods:**
```python
# Get season average
get_player_season_avg(player_id, stat_type)

# Get recent average (last 5 games)
get_player_recent_avg(player_id, stat_type, last_n_games=5)

# Get opponent defense
get_opponent_defense(opponent_abbr, stat_type)

# Calculate expected value
calculate_expected_value(player_id, stat_type, opponent)

# Analyze a prop line
analyze_prop_line(player_id, player_name, stat_type, line_value, opponent)

# Find all good plays for a date
find_best_plays(game_date, min_z_score=0.75)
```

### `simple_daily_picks.py`
Daily picks finder. Run this to get today's plays.

**Usage:**
```bash
python simple_daily_picks.py
```

---

## Example Output

```
Player         Stat    Line   Szn    L5    Exp    Dev      Z  Pick    Conf
-------------  ------  ----  -----  ----  -----  -----  -----  ------  ------
LeBron James   PTS     20.5   24.4  23.0   24.0   -3.5  -0.47  UNDER   Medium
Stephen Curry  PTS     32.5   27.8  29.2   28.2   +4.3  +0.86  OVER    High
Giannis        REB      9.5   11.2  12.4   11.5   -2.0  -1.12  UNDER   High
```

**Reasoning:**
1. **LeBron UNDER 20.5**: Vegas set line way below his averages → They know something → Bet UNDER
2. **Curry OVER 32.5**: Vegas set line way above his averages → They know something → Bet OVER
3. **Giannis UNDER 9.5**: Vegas set rebounds low despite his 11+ avg → Bet UNDER

---

## Using in PyCharm

### 1. Open Project
Open `/home/user/claamp-poll/nba-props/` in PyCharm

### 2. Test Individual Player
```python
from simple_analyzer import SimplePropsAnalyzer

analyzer = SimplePropsAnalyzer()

# Analyze a prop
result = analyzer.analyze_prop_line(
    player_id=2544,          # LeBron
    player_name="LeBron James",
    stat_type="points",
    line_value=22.5,
    opponent_team_abbr="BOS"
)

print(result)
# Shows: season avg, recent avg, expected, deviation, z-score, recommendation

analyzer.close()
```

### 3. Find All Good Plays
```python
from datetime import date
from simple_analyzer import SimplePropsAnalyzer

analyzer = SimplePropsAnalyzer()

# Find plays with z-score > 0.75 (3/4 standard deviation)
plays = analyzer.find_best_plays(
    game_date=date.today(),
    min_z_score=0.75
)

for play in plays:
    print(f"{play['player_name']} {play['stat_type']} {play['recommendation']}")
    print(f"  Deviation: {play['deviation']}, Z-score: {play['z_score']}")
    print(f"  {play['reasoning']}\n")

analyzer.close()
```

### 4. Run Daily Workflow
```bash
python simple_daily_picks.py
```

This shows all props sorted by deviation strength.

---

## Adjusting the Strategy

### Change Weights
In `calculate_expected_value()`:
```python
# Current: 40% season, 40% recent, 20% defense
expected = (season_avg * 0.4) + (recent_avg * 0.4) + (opp_defense * 0.2)

# More weight on recent form:
expected = (season_avg * 0.3) + (recent_avg * 0.5) + (opp_defense * 0.2)

# More weight on opponent defense:
expected = (season_avg * 0.35) + (recent_avg * 0.35) + (opp_defense * 0.3)
```

### Change Deviation Threshold
In `analyze_prop_line()`:
```python
# Current thresholds
if abs_z_score < 0.5:
    recommendation = "NO PLAY"
elif abs_z_score < 1.0:
    confidence = "Medium"
else:
    confidence = "High"

# More aggressive (lower threshold):
if abs_z_score < 0.3:
    recommendation = "NO PLAY"

# More conservative (higher threshold):
if abs_z_score < 1.0:
    recommendation = "NO PLAY"
```

### Change Recent Games Window
```python
# Current: Last 5 games
recent_avg = get_player_recent_avg(player_id, stat_type, last_n_games=5)

# Try 3 games (more weight on very recent):
recent_avg = get_player_recent_avg(player_id, stat_type, last_n_games=3)

# Try 10 games (broader recent trend):
recent_avg = get_player_recent_avg(player_id, stat_type, last_n_games=10)
```

---

## TODO: Improvements

### 1. Real Opponent Defense Stats
Currently uses league average. Should calculate:
- How many points/rebounds/assists each team allows per game
- Specific defensive ratings by position
- Home vs away defense splits

### 2. Home/Away Splits
Factor in:
- Player's home vs away performance
- Team's home vs away performance

### 3. Rest Days
- Back-to-back games (tired players)
- Coming off 2+ days rest (fresh players)

### 4. Injury Context
- Player dealing with minor injury
- Key teammate out (more usage)

### 5. Usage Rate
- If star player is out → higher usage for others
- Blowout potential → starters sit 4th quarter

---

## Philosophy

**This is NOT trying to predict what will happen.**

**This is following Vegas when they're telling us something unusual.**

If Vegas sets a line way off from what basic stats suggest, they usually have a reason:
- Injury news not yet public
- Coaching strategy (limiting minutes)
- Matchup advantage/disadvantage
- Motivation factors
- Rest/travel situations

**We follow the deviation, we don't fight it.**

---

## Next Steps

1. **Test with real data**: Run `simple_daily_picks.py` when you have today's prop lines
2. **Tune the weights**: Adjust season/recent/defense percentages
3. **Add opponent defense**: Replace league average with real team stats
4. **Track results**: Record picks and see which deviation levels work best
5. **Integrate with web app**: Connect to TakeFreePoints.com dashboard

---

**Simple, transparent, easy to understand. No black-box ML needed.**
