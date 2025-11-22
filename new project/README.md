# NBA Props Analyzer - Simple Stats-Based Approach

Clean, standalone NBA props analyzer. No web app, no complex ML.

## Quick Start

1. **Install dependencies:**
   ```bash
   pip install sqlalchemy nba_api requests pandas python-dotenv tabulate
   ```

2. **Set up environment:**
   ```bash
   cp .env.example .env
   # Edit .env and add your ODDS_API_KEY
   ```

3. **Collect today's data:**
   ```bash
   python collect_today.py
   ```

4. **Find plays:**
   ```bash
   python find_plays.py
   ```

---

## How It Works

### The Strategy

Find props where **Vegas line deviates significantly from expected value**.

**Theory:** When line is way off from stats → Vegas knows something → Follow the deviation.

### Expected Value Calculation

For each prop:
- **40%** Player's season average
- **40%** Player's last 5 games average
- **20%** Opponent defense (what they allow)

### Deviation Analysis

- **Line < Expected** → Vegas thinks underperformance → Bet **UNDER**
- **Line > Expected** → Vegas thinks overperformance → Bet **OVER**

**Z-score thresholds:**
- `< 0.5`: No edge
- `0.5-1.0`: Medium edge
- `> 1.0`: Strong edge

---

## Files

| File | Purpose |
|------|---------|
| `database/models.py` | Team, Player, Game, PropLine models |
| `database/db.py` | SQLite connection |
| `services/nba_api.py` | Fetch player stats |
| `services/odds_api.py` | Fetch prop lines |
| `analyzer.py` | Calculate expected values and deviations |
| `collect_today.py` | Fetch and store today's data |
| `find_plays.py` | Analyze and show best plays |
| `props.db` | SQLite database (auto-created) |

---

## Usage

### Collect Data
```bash
python collect_today.py
```

### Find Plays
```bash
# Default (z-score >= 0.5)
python find_plays.py

# Custom threshold (z-score >= 0.75)
python find_plays.py 0.75

# Very conservative (z-score >= 1.0)
python find_plays.py 1.0
```

### Example Output
```
Player         Stat    Line   Szn    L5    Exp    Dev      Z  Pick    Conf
-------------  ------  ----  -----  ----  -----  -----  -----  ------  ------
LeBron James   PTS     20.5   24.4  23.0   24.0   -3.5  -0.47  UNDER   Medium
Stephen Curry  PTS     32.5   27.8  29.2   28.2   +4.3  +0.86  OVER    High
```

---

## Customization

### Adjust Weights

In `analyzer.py`, change the weighting:

```python
# Current: 40% season, 40% recent, 20% defense
expected = (season_avg * 0.4) + (recent_avg * 0.4) + (opp_defense * 0.2)

# More recent form:
expected = (season_avg * 0.3) + (recent_avg * 0.5) + (opp_defense * 0.2)
```

### Change Recent Games Window

```python
# Current: Last 5 games
recent_avg = self.get_recent_avg(player_id, stat_type, last_n=5)

# Try last 3:
recent_avg = self.get_recent_avg(player_id, stat_type, last_n=3)
```

### Change Z-score Thresholds

In `analyzer.py`:

```python
# More aggressive (lower threshold):
if abs_z < 0.3:
    recommendation = "NO PLAY"

# More conservative (higher threshold):
if abs_z < 1.0:
    recommendation = "NO PLAY"
```

---

## TODO / Improvements

1. **Real opponent defense stats** (currently uses league average)
2. **Home/away splits** for players
3. **Rest days** consideration (back-to-backs, etc.)
4. **Injury context** (minor injuries, teammate out, etc.)
5. **Usage rate** adjustments

---

## Philosophy

**This is NOT trying to predict outcomes.**

**This is following Vegas when they signal something unusual.**

When Vegas sets a line way off from basic stats, they usually have a reason:
- Injury news not yet public
- Coaching strategy (minutes restriction)
- Matchup advantage/disadvantage
- Motivation factors

**We follow the deviation. We don't fight it.**

---

## Requirements

```
sqlalchemy>=2.0
nba_api>=1.4
requests>=2.31
pandas>=2.1
python-dotenv>=1.0
tabulate>=0.9
```

---

**Simple. Transparent. Easy to understand.**
