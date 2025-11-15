# NBA Player Props Prediction System

A data-driven system for collecting NBA player statistics and betting prop lines to build predictive models.

## Overview

This system collects and stores:
- **Player game-by-game statistics** from the NBA API (points, rebounds, assists, etc.)
- **Current betting prop lines** from The Odds API (over/under lines from multiple sportsbooks)
- **Historical data** for model training and backtesting

The goal is to build ML models that predict player performance and identify valuable betting opportunities.

## System Architecture

```
nba-props/
├── database/           # Database models and connection
│   ├── db.py          # SQLAlchemy setup
│   └── models.py      # Data models (Player, Game, PropLine, etc.)
├── services/          # API clients
│   ├── nba_api_client.py    # NBA stats fetching
│   └── odds_api_client.py   # Betting lines fetching
├── scripts/           # Executable scripts
│   ├── init_database.py         # Initialize DB and load teams/players
│   ├── backfill_historical.py  # Load historical game data
│   ├── collect_daily_data.py   # Daily collection workflow
│   └── query_data.py            # Inspect collected data
└── logs/              # Log files
```

## Prerequisites

- **Python 3.12.6** (or compatible version)
- **The Odds API key** (free tier: 500 requests/month)
  - Get yours at: https://the-odds-api.com/

## Installation

### 1. Navigate to the NBA props directory

```bash
cd /home/user/claamp-poll/nba-props
```

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

This installs:
- `nba_api` - Unofficial NBA stats API library
- `requests` - For HTTP requests to Odds API
- `SQLAlchemy` - Database ORM
- `pandas` - Data manipulation
- Other utilities

### 3. Configure environment variables

The `.env` file is already created with your Odds API key. Verify it:

```bash
cat .env
```

You should see:
```
ODDS_API_KEY=4c115ca6a0d3a4b81ad29e7ac826d2f8
NBA_DATABASE_URL=sqlite:///nba_props.db
```

## Getting Started

### Step 1: Initialize the Database

This creates the database schema and populates teams and players:

```bash
python scripts/init_database.py
```

**What it does:**
- Creates SQLite database: `nba_props.db`
- Creates all tables (teams, players, games, stats, props, predictions, results)
- Loads all 30 NBA teams
- Loads all active NBA players (~450 players)

**Expected time:** 3-5 minutes (due to API rate limiting)

### Step 2: Backfill Historical Data

Load past season data for model training:

```bash
# Load current season (2024-25)
python scripts/backfill_historical.py --season 2024-25

# Load previous season (2023-24)
python scripts/backfill_historical.py --season 2023-24
```

**What it does:**
- Fetches game-by-game stats for all active players
- Creates game records
- Stores player performance data (points, rebounds, assists, etc.)

**Expected time:** 30-60 minutes per season (API rate limiting)

**Tip:** Start with a small test:
```bash
python scripts/backfill_historical.py --season 2024-25 --limit 10
```

### Step 3: Collect Today's Props

Fetch current betting lines and upcoming games:

```bash
python scripts/collect_daily_data.py
```

**What it does:**
1. Fetches upcoming NBA games from Odds API
2. Creates game records in database
3. Fetches player prop lines for each game (points, rebounds, assists, etc.)
4. Stores prop lines with odds from multiple sportsbooks
5. Shows API usage stats

**Expected time:** 1-2 minutes

**Options:**
```bash
# Collect props for next 2 days
python scripts/collect_daily_data.py --days-ahead 2

# Also update stats for recently completed games
python scripts/collect_daily_data.py --update-completed
```

## Querying Your Data

Use the query tool to inspect collected data:

```bash
# Interactive mode
python scripts/query_data.py

# Command-line mode
python scripts/query_data.py stats              # Database statistics
python scripts/query_data.py games              # Recent games
python scripts/query_data.py props              # Today's props
python scripts/query_data.py player LeBron      # Player stats
python scripts/query_data.py top points         # Top scorers
```

### Example Output

```
TODAY'S PLAYER PROPS (2024-11-15)
============================================================

LAL @ BOS
------------------------------------------------------------

  LeBron James:
    points          25.5  (draftkings) [O-110 / U-110]
    rebounds         7.5  (draftkings) [O-120 / U+100]
    assists          7.5  (draftkings) [O-105 / U-115]
    pts_reb_ast     40.5  (fanduel) [O-115 / U-105]

  Anthony Davis:
    points          27.5  (draftkings) [O-105 / U-115]
    rebounds        11.5  (draftkings) [O-110 / U-110]
    ...
```

## Database Schema

### Core Tables

**nba_teams** - NBA teams reference data
- `nba_team_id` - Official NBA team ID
- `name`, `abbreviation`, `city`, `conference`, `division`

**nba_players** - Active NBA players
- `nba_player_id` - Official NBA player ID
- `full_name`, `team_id`, `position`, `jersey_number`
- `is_active` - Currently active player flag

**nba_games** - NBA games (past and upcoming)
- `nba_game_id` - NBA game identifier
- `game_date`, `game_time`, `season`
- `home_team_id`, `away_team_id`
- `status` - scheduled, in_progress, final, postponed
- `home_score`, `away_score` - Final scores

**nba_player_game_stats** - Actual player performance
- `player_id`, `game_id`
- `minutes`, `points`, `rebounds`, `assists`
- `field_goals_made/attempted`, `three_pointers_made/attempted`
- `steals`, `blocks`, `turnovers`, `plus_minus`

**nba_prop_lines** - Betting lines from sportsbooks
- `player_id`, `game_id`
- `prop_type` - points, rebounds, assists, pts_reb_ast, etc.
- `line_value` - The over/under number (e.g., 25.5)
- `over_odds`, `under_odds` - American odds (e.g., -110)
- `sportsbook` - draftkings, fanduel, etc.
- `fetched_at`, `is_latest` - Timestamp tracking

**nba_predictions** - Your model's predictions (for future use)
- `player_id`, `game_id`, `prop_type`
- `predicted_value` - Model's prediction
- `recommended_pick` - "over" or "under"
- `confidence_score`, `model_version`

**nba_results** - Track prediction accuracy (for future use)
- `prediction_id`
- `actual_value`, `was_correct`
- `profit_loss` - If betting

## Daily Workflow

Once you have historical data loaded, run this daily (before games start):

```bash
# Morning: Collect today's props
python scripts/collect_daily_data.py

# Inspect what was collected
python scripts/query_data.py props

# Evening: Update completed game stats (after games finish)
python scripts/collect_daily_data.py --update-completed
```

## API Usage Tracking

### The Odds API (Free Tier)
- **Limit:** 500 requests/month
- **Usage:** ~10-20 requests per daily collection (depends on number of games)
- **Check remaining:** Displayed after each collection run

**Tip:** To conserve API calls during testing, you can:
1. Only run daily collection when you actually need fresh data
2. The historical backfill doesn't use Odds API (only NBA API)

### NBA API
- **Limit:** Unofficial, no documented limits but enforce rate limiting
- **Rate limiting:** Built-in 600ms delay between requests
- **Best practice:** Don't spam the API; use the built-in rate limiting

## Data for Model Training

The collected data provides everything you need for ML models:

### Features You Can Build
- **Player averages:** Last 5, 10, 15 games
- **Home/Away splits:** Performance at home vs. away
- **Opponent strength:** How opponents defend specific positions
- **Days rest:** Back-to-back games vs. rest days
- **Minutes trend:** Playing time patterns
- **Recent form:** Hot/cold streaks
- **Matchup history:** How player performs vs. specific teams

### Example Query for Model Features

```python
from database import get_session, Player, Game, PlayerGameStats
from sqlalchemy import func

session = get_session()

# Get player's last 10 games stats
player = session.query(Player).filter_by(full_name="LeBron James").first()

recent_stats = session.query(PlayerGameStats).join(Game).filter(
    PlayerGameStats.player_id == player.id,
    Game.status == 'final'
).order_by(Game.game_date.desc()).limit(10).all()

# Calculate averages
avg_points = sum(s.points for s in recent_stats) / len(recent_stats)
avg_rebounds = sum(s.rebounds for s in recent_stats) / len(recent_stats)
avg_assists = sum(s.assists for s in recent_stats) / len(recent_stats)

print(f"Last 10 games: {avg_points:.1f} pts, {avg_rebounds:.1f} reb, {avg_assists:.1f} ast")
```

## Troubleshooting

### "No games found"
- Check the NBA schedule - there might not be games today
- Try `--days-ahead 2` to look further ahead

### "Could not find player: [Name]"
- Player names from Odds API might differ from NBA API
- This is normal for bench players who don't have props
- Main players (stars) should match fine

### "API requests remaining: 0"
- You've hit the Odds API monthly limit
- Wait until next month or upgrade to paid tier
- Historical backfill doesn't use Odds API

### Database errors
- Make sure you ran `init_database.py` first
- Delete `nba_props.db` and start over if corrupted

### Slow backfill
- This is normal - NBA API rate limiting (600ms between requests)
- Backfilling a full season takes 30-60 minutes
- You can run it in the background

## Future Enhancements

Things you'll want to add:

1. **ML Models** - Train prediction models (XGBoost, Random Forest, Neural Networks)
2. **Feature Engineering** - Advanced stats, matchup analysis, player archetypes
3. **Web Dashboard** - Integrate predictions into your Flask app
4. **Automated Scheduling** - Cron job for daily collection
5. **Backtesting Framework** - Test model performance on historical props
6. **Line Movement Tracking** - Track how lines change over time
7. **Injury Data** - Scrape injury reports (major impact on props)
8. **Advanced Metrics** - Usage rate, pace, defensive rating

## File Locations

- **Database:** `/home/user/claamp-poll/nba-props/nba_props.db`
- **Logs:** `/home/user/claamp-poll/nba-props/logs/`
- **Config:** `/home/user/claamp-poll/nba-props/.env`

## Questions & Common Issues

### How do I avoid duplicate data?
The system has built-in duplicate prevention:
- Games: Unique constraint on (home_team, away_team, game_date)
- Player stats: Unique constraint on (player_id, game_id)
- Props: Marked as `is_latest=False` when new lines fetched

### How do I handle postponed games?
- Games have a `status` field (scheduled, in_progress, final, postponed)
- You can manually update status if needed
- The collection script doesn't auto-detect postponements yet

### How do I match players between APIs?
- The system does fuzzy matching on player names
- Most stars match automatically
- For edge cases, you may need manual mapping (future enhancement)

### What if I want to use PostgreSQL instead of SQLite?
Update `.env`:
```
NBA_DATABASE_URL=postgresql://user:password@localhost/nba_props
```

### Can I run this on a server/cloud?
Yes! Just:
1. Copy the `/nba-props/` directory
2. Install Python dependencies
3. Set up a cron job for daily collection
4. Consider PostgreSQL for better concurrent access

## Support

For issues with:
- **NBA API:** https://github.com/swar/nba_api
- **The Odds API:** https://the-odds-api.com/
- **This system:** Check logs in `logs/` directory

## License

This is a personal project for educational/research purposes. Respect API terms of service.

---

**Happy predicting! 🏀📊**
