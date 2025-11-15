# Quick Start Guide

Get up and running in 5 minutes!

## Installation

```bash
cd /home/user/claamp-poll/nba-props
pip install -r requirements.txt
```

## Setup (First Time Only)

```bash
# Step 1: Initialize database and load teams/players (~3-5 min)
python scripts/init_database.py

# Step 2: Load some historical data (optional, for testing)
python scripts/backfill_historical.py --season 2024-25 --limit 10
```

## Daily Usage

```bash
# Collect today's games and prop lines
python scripts/collect_daily_data.py

# View what you collected
python scripts/query_data.py props
```

## Inspect Your Data

```bash
# Interactive mode
python scripts/query_data.py

# Quick commands
python scripts/query_data.py stats              # Database stats
python scripts/query_data.py player "LeBron"    # Player recent stats
python scripts/query_data.py top points         # Top scorers
```

## Tips

- **API Limits:** 500 Odds API requests/month (free tier)
- **Daily Cost:** ~10-20 requests per collection
- **Best Time:** Run collection in the morning before games
- **Historical Data:** Doesn't use Odds API, safe to backfill anytime

## Next Steps

1. Collect data for a few days
2. Build features for ML models (averages, trends, matchups)
3. Train prediction models
4. Integrate predictions into your web app
5. Track accuracy in the `nba_results` table

See `README.md` for full documentation.
