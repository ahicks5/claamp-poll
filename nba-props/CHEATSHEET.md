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
- **Daily Cost:** ~10-20 requests per collection
- **NBA API:** Unlimited (but rate limited to 600ms between calls)

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

```bash
# First time setup
pip install -r requirements.txt
python scripts/init_database.py

# Collect data for 2-3 weeks
python scripts/collect_daily_data.py  # Run daily
python scripts/backfill_historical.py --season 2024-25

# Train model (after collecting enough data)
python scripts/train_model.py --prop-type points

# Daily routine (morning)
python scripts/collect_daily_data.py
python scripts/generate_predictions.py --prop-type points
python scripts/query_data.py props

# Weekly maintenance
python scripts/train_model.py --prop-type points
python scripts/backtest_model.py --days-back 30
```
