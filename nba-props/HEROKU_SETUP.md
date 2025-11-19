# Heroku Deployment Guide

Complete guide for deploying the NBA Props prediction system to Heroku.

## Overview

This guide covers:
1. Database configuration (PostgreSQL on Heroku, MySQL/SQLite locally)
2. NBA API timeout fixes for Heroku's network
3. Initialization and testing
4. Troubleshooting common issues

## Prerequisites

- Heroku CLI installed (`heroku --version`)
- Git repository initialized
- Heroku app created (`heroku create your-app-name`)

## Step 1: Database Setup

### On Heroku (PostgreSQL)

```bash
# Add PostgreSQL addon
heroku addons:create heroku-postgresql:essential-0

# This automatically sets DATABASE_URL environment variable
# We need to copy it to NBA_DATABASE_URL

# Get the database URL
heroku config:get DATABASE_URL

# Set NBA_DATABASE_URL (copy the value from above)
heroku config:set NBA_DATABASE_URL="<paste-database-url-here>"
```

### Local Development (MySQL or SQLite)

**Option 1: MySQL**
```bash
# In your .env file (nba-props/.env)
NBA_DATABASE_URL=mysql+pymysql://user:password@localhost/nba_props
```

**Option 2: SQLite (easiest for local dev)**
```bash
# In your .env file
NBA_DATABASE_URL=sqlite:///nba_props.db
```

The system automatically detects which database you're using and configures appropriately.

## Step 2: Environment Variables

Set all required environment variables on Heroku:

```bash
# Required
heroku config:set ODDS_API_KEY="your_odds_api_key_here"

# NBA API configuration (for Heroku's slower network)
heroku config:set NBA_API_TIMEOUT=90
heroku config:set NBA_API_MAX_RETRIES=2

# Optional
heroku config:set LOG_LEVEL=INFO
```

Verify environment variables:
```bash
heroku config
```

## Step 3: Deploy to Heroku

```bash
# Make sure you're in the project root
cd /home/user/claamp-poll

# Add and commit changes
git add .
git commit -m "Configure for Heroku deployment"

# Push to Heroku
git push heroku main

# Or if you're on a different branch:
git push heroku your-branch:main
```

## Step 4: Initialize Database on Heroku

### Option A: Quick Initialization (Just create tables)

```bash
heroku run python nba-props/scripts/heroku_init.py
```

This will:
- Test database connection
- Create all tables
- Test NBA API connectivity

### Option B: Full Initialization (Tables + Reference Data)

```bash
heroku run python nba-props/scripts/heroku_init.py --full
```

This will:
- Create all tables
- Load all 30 NBA teams
- Load all ~450 active players
- Takes 5-10 minutes due to rate limiting

### Option C: Partial Initialization (For Testing)

```bash
# Load only 50 players for quick testing
heroku run python nba-props/scripts/heroku_init.py --load-reference --player-limit 50
```

## Step 5: Test the Deployment

Run the diagnostic script to verify everything works:

```bash
heroku run python nba-props/scripts/diagnose_heroku.py
```

This tests:
- ✓ Environment variables
- ✓ Database connectivity (PostgreSQL)
- ✓ NBA API connectivity
- ✓ Odds API connectivity
- ✓ Network access
- ✓ File system permissions

Expected output:
```
==============================================================
DIAGNOSTIC SUMMARY
==============================================================
  ✓ PASS   Environment
  ✓ PASS   Database
  ✓ PASS   NBA API
  ✓ PASS   Odds API
  ✓ PASS   Network
  ✓ PASS   File System

Passed: 6/6

[SUCCESS] All diagnostic tests passed!
```

## Step 6: Collect Data

### Collect Today's Props

```bash
heroku run python nba-props/scripts/collect_daily_data.py
```

### Backfill Historical Data

```bash
# Current season
heroku run python nba-props/scripts/backfill_historical.py --season 2024-25

# Previous season (for training)
heroku run python nba-props/scripts/backfill_historical.py --season 2023-24
```

**Note:** Backfilling takes 30-60 minutes per season due to rate limiting.

## Step 7: Train Model

```bash
heroku run python nba-props/scripts/train_model.py --prop-type points --days-back 365
```

## Step 8: Generate Predictions

```bash
heroku run python nba-props/scripts/generate_predictions.py --prop-type points
```

## Common Issues & Solutions

### Issue 1: NBA API Timeouts

**Error:**
```
ReadTimeout: HTTPSConnectionPool(host='stats.nba.com', port=443): Read timed out
```

**Solution:**
```bash
# Increase timeout (default: 90s)
heroku config:set NBA_API_TIMEOUT=120

# Increase retries (default: 2)
heroku config:set NBA_API_MAX_RETRIES=3
```

### Issue 2: Database Connection Errors

**Error:**
```
sqlalchemy.exc.OperationalError: (psycopg2.OperationalError) could not connect to server
```

**Solution:**
```bash
# Verify DATABASE_URL is set
heroku config:get DATABASE_URL

# Make sure NBA_DATABASE_URL matches
heroku config:set NBA_DATABASE_URL="$(heroku config:get DATABASE_URL)"

# Test connection
heroku run python nba-props/scripts/diagnose_heroku.py
```

### Issue 3: Missing Dependencies

**Error:**
```
ModuleNotFoundError: No module named 'psycopg2'
```

**Solution:**
```bash
# Make sure requirements.txt includes:
# - psycopg2-binary (for PostgreSQL)
# - PyMySQL (for MySQL)
# - gunicorn (for web server)

# Force Heroku to reinstall dependencies
git commit --allow-empty -m "Force rebuild"
git push heroku main
```

### Issue 4: Heroku Timeout (H12 Error)

**Error:**
```
Error H12 - Request timeout
```

**Solution:**
```bash
# Don't run long operations via web requests
# Use Heroku scheduler for daily tasks instead

# Add scheduler addon
heroku addons:create scheduler:standard

# Open scheduler dashboard
heroku addons:open scheduler

# Add daily job:
# Command: python nba-props/scripts/collect_daily_data.py
# Frequency: Daily at 10:00 AM
```

### Issue 5: Out of Memory

**Error:**
```
Error R14 - Memory quota exceeded
```

**Solution:**
```bash
# Upgrade dyno type
heroku ps:resize worker=standard-1x

# Or optimize memory usage in code
# - Reduce batch sizes
# - Clear sessions after use
# - Limit lookback_games parameter
```

## Database Migrations

If you need to modify database schema:

```bash
# Option 1: Drop and recreate (DESTROYS DATA!)
heroku pg:reset DATABASE
heroku run python nba-props/scripts/heroku_init.py --full

# Option 2: Manual migration (safer)
heroku run python
>>> from nba_props.database import engine
>>> from sqlalchemy import text
>>> with engine.connect() as conn:
...     conn.execute(text("ALTER TABLE nba_players ADD COLUMN new_field VARCHAR(100)"))
...     conn.commit()
```

## Scheduled Tasks

Set up daily data collection:

```bash
# Install scheduler addon
heroku addons:create scheduler:standard

# Open scheduler
heroku addons:open scheduler
```

Add these jobs:

| Frequency | Time | Command |
|-----------|------|---------|
| Daily | 10:00 AM | `python nba-props/scripts/collect_daily_data.py` |
| Daily | 11:00 PM | `python nba-props/scripts/collect_daily_data.py --update-completed` |
| Weekly | Sunday 2:00 AM | `python nba-props/scripts/train_model.py --prop-type points` |

## Monitoring

### View Logs

```bash
# Real-time logs
heroku logs --tail

# Filter by app
heroku logs --tail --source app

# Last 1000 lines
heroku logs -n 1000
```

### Database Access

```bash
# Connect to PostgreSQL
heroku pg:psql

# Run queries
SELECT COUNT(*) FROM nba_teams;
SELECT COUNT(*) FROM nba_players;
SELECT COUNT(*) FROM nba_games;
```

### Check Dyno Status

```bash
heroku ps
```

## Performance Optimization

### 1. Connection Pooling

Already configured in `database/db.py`:
- Pool size: 5 connections
- Max overflow: 10
- Pool recycle: 1 hour

### 2. NBA API Rate Limiting

Already configured in `services/nba_api_client.py`:
- 600ms delay between requests
- 90s timeout
- 2 retry attempts with exponential backoff

### 3. Reduce API Calls

```bash
# Cache player data locally (only fetch details when needed)
heroku run python nba-props/scripts/heroku_init.py --load-reference --skip-details

# Limit historical backfill
heroku run python nba-props/scripts/backfill_historical.py --season 2024-25 --limit 1000
```

## Testing Locally with PostgreSQL

To test PostgreSQL setup locally:

```bash
# Install PostgreSQL locally
# macOS: brew install postgresql
# Ubuntu: sudo apt-get install postgresql

# Start PostgreSQL
# macOS: brew services start postgresql
# Ubuntu: sudo service postgresql start

# Create database
createdb nba_props

# Update .env
NBA_DATABASE_URL=postgresql://localhost/nba_props

# Test
python nba-props/scripts/diagnose_heroku.py
```

## Switching Between Databases

The system automatically detects database type:

```python
# In database/db.py

if DATABASE_URL.startswith("postgresql://"):
    # Use PostgreSQL settings (Heroku)

elif DATABASE_URL.startswith("mysql://"):
    # Use MySQL settings (local)

elif DATABASE_URL.startswith("sqlite://"):
    # Use SQLite settings (local dev)
```

Just change `NBA_DATABASE_URL` in your `.env` file and the code adapts.

## Cost Optimization

### Free Tier Limits

- **Heroku Dyno:** 550 free hours/month
- **PostgreSQL:** 10,000 rows (hobby-dev)
- **Odds API:** 500 requests/month

### Upgrade When Needed

```bash
# PostgreSQL (when you hit 10k rows)
heroku addons:create heroku-postgresql:essential-0  # $5/month

# Dyno (for 24/7 operation)
heroku ps:resize web=hobby  # $7/month
```

## Backup & Recovery

### Backup Database

```bash
# Create backup
heroku pg:backups:capture

# Download backup
heroku pg:backups:download

# List backups
heroku pg:backups
```

### Restore Database

```bash
# Restore from backup
heroku pg:backups:restore <backup-id> DATABASE_URL
```

## Next Steps

1. Set up monitoring (e.g., Papertrail addon)
2. Configure automatic backups
3. Set up Heroku Scheduler for daily tasks
4. Add error tracking (e.g., Sentry)
5. Create web dashboard for predictions

## Support

- **Heroku Docs:** https://devcenter.heroku.com/
- **NBA API:** https://github.com/swar/nba_api
- **The Odds API:** https://the-odds-api.com/

## Quick Reference

```bash
# Essential commands
heroku logs --tail                                    # View logs
heroku run bash                                       # SSH into dyno
heroku pg:psql                                        # Access database
heroku config                                         # View env vars
heroku ps                                             # Check dyno status
heroku restart                                        # Restart app

# Diagnostic commands
heroku run python nba-props/scripts/diagnose_heroku.py     # Full diagnostics
heroku run python nba-props/scripts/test_nba_api.py        # NBA API test

# Data commands
heroku run python nba-props/scripts/collect_daily_data.py  # Collect today's props
heroku run python nba-props/scripts/query_data.py stats    # View database stats
```

---

**Last Updated:** 2025-11-19
