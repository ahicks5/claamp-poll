# Testing Checklist

Use this checklist to verify your Heroku setup is working correctly.

## Local Testing (Before Deploying to Heroku)

### 1. Install Dependencies

```bash
cd /home/user/claamp-poll/nba-props
pip install -r requirements.txt
```

**New dependencies added:**
- ✅ `psycopg2-binary` - PostgreSQL driver (Heroku)
- ✅ `PyMySQL` - MySQL driver (local)
- ✅ `gunicorn` - WSGI server (Heroku)

### 2. Configure Local Database

**Option A: SQLite (Easiest)**
```bash
# In nba-props/.env
NBA_DATABASE_URL=sqlite:///nba_props.db
```

**Option B: MySQL**
```bash
# In nba-props/.env
NBA_DATABASE_URL=mysql+pymysql://root:password@localhost/nba_props

# Create database first:
mysql -u root -p -e "CREATE DATABASE nba_props;"
```

**Option C: PostgreSQL (Test Heroku locally)**
```bash
# In nba-props/.env
NBA_DATABASE_URL=postgresql://localhost/nba_props

# Create database first:
createdb nba_props
```

### 3. Run Diagnostic Script

```bash
cd /home/user/claamp-poll/nba-props
python scripts/diagnose_heroku.py
```

**Expected output:**
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
```

**If tests fail:**
- Check `.env` file has all required variables
- Verify database is running and accessible
- Check internet connectivity
- Review error messages in output

### 4. Test Database Connection

```bash
cd /home/user/claamp-poll/nba-props
python -c "
from database import get_session, init_db
init_db()
session = get_session()
print('✓ Database connection successful!')
session.close()
"
```

### 5. Test NBA API

```bash
cd /home/user/claamp-poll/nba-props
python scripts/test_nba_api.py
```

**Expected output:**
- ✓ Teams fetched successfully
- ✓ Players fetched successfully
- ✓ Games fetched successfully

## Heroku Testing

### 1. Set Environment Variables

```bash
# Required
heroku config:set NBA_DATABASE_URL="$(heroku config:get DATABASE_URL)"
heroku config:set ODDS_API_KEY="your_api_key_here"

# NBA API configuration
heroku config:set NBA_API_TIMEOUT=90
heroku config:set NBA_API_MAX_RETRIES=2
```

**Verify:**
```bash
heroku config
```

### 2. Deploy to Heroku

```bash
cd /home/user/claamp-poll
git add .
git commit -m "Configure for Heroku: database drivers and NBA API timeouts"
git push heroku claude/code-walkthrough-016dKqvqcRV9NsZa4U72YtFX:main
```

### 3. Run Heroku Diagnostics

```bash
heroku run python nba-props/scripts/diagnose_heroku.py
```

**Check for:**
- ✓ Environment variables are set correctly
- ✓ PostgreSQL connection works
- ✓ NBA API doesn't timeout
- ✓ Odds API accessible
- ✓ Network connectivity OK

### 4. Initialize Database on Heroku

```bash
# Quick test (just create tables)
heroku run python nba-props/scripts/heroku_init.py

# Full initialization (load teams + players)
heroku run python nba-props/scripts/heroku_init.py --full
```

**Expected output:**
```
==============================================================
Testing Database Connection
==============================================================
  ✓ Database connection successful!

==============================================================
Creating Database Tables
==============================================================
  ✓ All tables created successfully

==============================================================
Testing NBA API Connection
==============================================================
  ✓ NBA API connection successful!
  Found 30 teams

==============================================================
[SUCCESS] Heroku initialization complete!
```

### 5. Test Data Collection

```bash
# Collect today's props
heroku run python nba-props/scripts/collect_daily_data.py
```

**Expected output:**
- Found X games today
- Fetched props for Y players
- Saved to database

### 6. Query Data

```bash
heroku run python nba-props/scripts/query_data.py stats
```

**Expected output:**
```
DATABASE STATISTICS
==================
Teams:        30
Players:      450
Games:        X
Props:        Y
```

### 7. Test Model Training (If you have enough data)

```bash
heroku run python nba-props/scripts/train_model.py --prop-type points --days-back 90
```

**Expected:**
- Training data prepared
- Model trained successfully
- Accuracy metrics displayed
- Model saved

## Common Test Failures & Fixes

### ❌ Test 1: Database Connection Failed

**Error:** `sqlalchemy.exc.OperationalError`

**Fix:**
```bash
# Heroku
heroku config:set NBA_DATABASE_URL="$(heroku config:get DATABASE_URL)"

# Local (MySQL)
mysql -u root -p -e "CREATE DATABASE nba_props;"

# Local (SQLite)
# Just make sure NBA_DATABASE_URL=sqlite:///nba_props.db
```

### ❌ Test 2: NBA API Timeout

**Error:** `ReadTimeout: Read timed out`

**Fix:**
```bash
# Increase timeout
heroku config:set NBA_API_TIMEOUT=120

# Increase retries
heroku config:set NBA_API_MAX_RETRIES=3

# For local testing, add to .env:
NBA_API_TIMEOUT=120
NBA_API_MAX_RETRIES=3
```

### ❌ Test 3: Odds API Failed

**Error:** `401 Unauthorized` or `Invalid API Key`

**Fix:**
```bash
# Check API key is set correctly
heroku config:get ODDS_API_KEY

# Set it again
heroku config:set ODDS_API_KEY="your_key_here"

# Verify key works:
curl "https://api.the-odds-api.com/v4/sports?apiKey=YOUR_KEY"
```

### ❌ Test 4: Module Not Found

**Error:** `ModuleNotFoundError: No module named 'psycopg2'`

**Fix:**
```bash
# Make sure requirements.txt includes all dependencies
cat nba-props/requirements.txt | grep -E "(psycopg2|PyMySQL|gunicorn)"

# Should see:
# psycopg2-binary==2.9.9
# PyMySQL==1.1.0
# gunicorn==21.2.0

# Force rebuild on Heroku
git commit --allow-empty -m "Force rebuild"
git push heroku main
```

### ❌ Test 5: Heroku Memory Error (R14)

**Error:** `Error R14 - Memory quota exceeded`

**Fix:**
```bash
# Upgrade dyno
heroku ps:resize web=standard-1x

# Or reduce batch sizes in code
# Edit scripts to use --limit flags:
heroku run python nba-props/scripts/heroku_init.py --player-limit 50
```

## Verification Steps

### Step 1: Verify Database Schema

```bash
# On Heroku
heroku pg:psql

# Run these queries:
\dt                                    # List all tables
SELECT COUNT(*) FROM nba_teams;        # Should be 30
SELECT COUNT(*) FROM nba_players;      # Should be ~450
\q                                     # Exit
```

### Step 2: Verify NBA API Works

```bash
heroku run python nba-props/scripts/test_nba_api.py
```

Should complete without timeouts.

### Step 3: Verify Odds API Works

```bash
heroku run python -c "
import os
import requests
key = os.getenv('ODDS_API_KEY')
r = requests.get('https://api.the-odds-api.com/v4/sports', params={'apiKey': key})
print(f'Status: {r.status_code}')
print(f'Remaining: {r.headers.get(\"x-requests-remaining\")}')
"
```

Should return status 200 and remaining requests.

### Step 4: End-to-End Test

Run the complete workflow:

```bash
# 1. Collect data
heroku run python nba-props/scripts/collect_daily_data.py

# 2. Check what was collected
heroku run python nba-props/scripts/query_data.py props

# 3. If you have historical data, train model
heroku run python nba-props/scripts/train_model.py --prop-type points

# 4. Generate predictions
heroku run python nba-props/scripts/generate_predictions.py --prop-type points
```

## Performance Benchmarks

Expected execution times:

| Command | Local | Heroku |
|---------|-------|--------|
| `diagnose_heroku.py` | 10-15s | 20-30s |
| `heroku_init.py` (tables only) | 5s | 10s |
| `heroku_init.py --full` | 5-10min | 10-15min |
| `collect_daily_data.py` | 30s | 60s |
| `train_model.py` | 2-5min | 5-10min |
| `generate_predictions.py` | 10s | 20s |

**If commands take significantly longer:**
- Check NBA_API_TIMEOUT setting
- Verify network connectivity
- Check dyno type (free vs paid)

## Success Criteria

✅ **Local Setup Complete:**
- [ ] All dependencies installed
- [ ] Database connection works
- [ ] NBA API test passes
- [ ] Odds API test passes
- [ ] Can initialize database
- [ ] Can collect sample data

✅ **Heroku Setup Complete:**
- [ ] App deployed successfully
- [ ] Environment variables set
- [ ] Database initialized
- [ ] All diagnostics pass
- [ ] Can collect today's props
- [ ] Can train model
- [ ] Can generate predictions

## Next Steps After Testing

1. **Set up Heroku Scheduler** for daily data collection
2. **Configure backups** for PostgreSQL database
3. **Add monitoring** (logs, error tracking)
4. **Optimize performance** (caching, connection pooling)
5. **Build web dashboard** for viewing predictions

## Support Resources

- **Diagnostic Script:** `python scripts/diagnose_heroku.py`
- **Test NBA API:** `python scripts/test_nba_api.py`
- **Heroku Logs:** `heroku logs --tail`
- **Database Access:** `heroku pg:psql`

---

**Last Updated:** 2025-11-19
