# NBA Props System - Command Cheat Sheet

## Installation (One-Time)
```bash
cd /home/user/claamp-poll/nba-props
pip install -r requirements.txt
```

## Setup (One-Time)
```bash
# Initialize database and load teams/players
python scripts/init_database.py
```

## Daily Commands

### Collect Today's Data
```bash
# Basic collection
python scripts/collect_daily_data.py

# Collect next 2 days
python scripts/collect_daily_data.py --days-ahead 2

# Update completed games
python scripts/collect_daily_data.py --update-completed
```

### View Data
```bash
# Interactive mode
python scripts/query_data.py

# Quick commands
python scripts/query_data.py stats              # Database stats
python scripts/query_data.py games              # Recent games
python scripts/query_data.py props              # Today's props
python scripts/query_data.py player "LeBron"   # Player stats
python scripts/query_data.py top points         # Top scorers
```

## Historical Data

### Backfill Seasons
```bash
# Current season
python scripts/backfill_historical.py --season 2024-25

# Last season
python scripts/backfill_historical.py --season 2023-24

# Test with limit
python scripts/backfill_historical.py --season 2024-25 --limit 10
```

## Database Access (Python)

### Quick Query Example
```python
from database import get_session, Player, PlayerGameStats, Game, PropLine
from sqlalchemy import desc

session = get_session()

# Get player
player = session.query(Player).filter_by(full_name="LeBron James").first()

# Get recent stats
stats = session.query(PlayerGameStats).join(Game).filter(
    PlayerGameStats.player_id == player.id
).order_by(desc(Game.game_date)).limit(10).all()

# Get today's props
from datetime import datetime
today = datetime.now().date()
props = session.query(PropLine).join(Game).filter(
    Game.game_date == today,
    PropLine.is_latest == True
).all()

session.close()
```

## Files & Locations

```bash
# Database
/home/user/claamp-poll/nba-props/nba_props.db

# Logs
/home/user/claamp-poll/nba-props/logs/daily_collection.log

# Config
/home/user/claamp-poll/nba-props/.env
```

## Troubleshooting

### Check API Usage
Output shows after each collection:
```
Odds API Usage:
  Requests used (this session): 12
  Requests remaining: 488
```

### View Logs
```bash
tail -f logs/daily_collection.log
```

### Reset Database
```bash
rm nba_props.db
python scripts/init_database.py
```

## API Limits

- **Odds API Free Tier:** 500 requests/month
- **Odds API Pro Tier:** 20,000 requests/month ($30/month)
- **Daily Cost:** ~10-20 requests per collection
- **NBA API:** Unlimited (but rate limited to 600ms between calls)

## Historical Data Collection

### Backfill Historical Odds (Requires Pro Plan)
```bash
# Backfill current season's historical prop odds
python scripts/backfill_historical_odds.py --season 2025-26

# Test with limited games first
python scripts/backfill_historical_odds.py --season 2025-26 --limit 5

# Slower rate (be gentle on API)
python scripts/backfill_historical_odds.py --season 2025-26 --delay 2.0
```

## Machine Learning Commands

### Train Models
```bash
# Train on points props (most common)
python scripts/train_model.py --prop-type points

# Train on other prop types
python scripts/train_model.py --prop-type rebounds
python scripts/train_model.py --prop-type assists
```

### Generate Predictions
```bash
# Get today's predictions
python scripts/generate_predictions.py --prop-type points --min-confidence 0.65

# Save to database
python scripts/generate_predictions.py --prop-type points --save-to-db
```

### Backtest Model
```bash
# Test on last 30 days
python scripts/backtest_model.py --prop-type points --days-back 30

# Custom settings
python scripts/backtest_model.py --days-back 60 --min-confidence 0.70 --unit-size 100
```

## Quick Start Flow

### Option A: With Historical Odds (Pro Plan)
```bash
# First time setup
pip install -r requirements.txt
python scripts/init_database.py

# Backfill historical game stats
python scripts/backfill_historical.py --season 2025-26

# Backfill historical prop odds (requires Pro plan)
python scripts/backfill_historical_odds.py --season 2025-26

# Train full model with odds
python scripts/train_model.py --prop-type points

# Daily routine (morning)
python scripts/collect_daily_data.py
python scripts/generate_predictions.py --prop-type points --min-confidence 0.65
python scripts/query_data.py props

# Weekly maintenance
python scripts/train_model.py --prop-type points
python scripts/backtest_model.py --days-back 30
```

### Option B: Stats-Only (Free)
```bash
# First time setup
pip install -r requirements.txt
python scripts/init_database.py

# Backfill historical game stats
python scripts/backfill_historical.py --season 2025-26

# Train regression model (no odds needed)
python scripts/train_model_no_odds.py --prop-type points

# Collect daily odds going forward
python scripts/collect_daily_data.py  # Run daily

# Daily predictions using regression model
python scripts/generate_predictions_regression.py --prop-type points --min-edge 2.0

# After 2-3 weeks, upgrade to full model
python scripts/train_model.py --prop-type points
```
