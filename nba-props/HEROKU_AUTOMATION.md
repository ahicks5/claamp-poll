# Heroku Deployment & Automation Guide

## Overview

This guide shows you how to:
1. Deploy your NBA Props system to Heroku
2. Set up automated daily workflows
3. Integrate with your existing web app

---

## Option 1: Heroku Scheduler (Recommended)

### What is Heroku Scheduler?

Heroku Scheduler is a free add-on that runs commands on a schedule (like cron jobs).

**Pros:**
- Free tier available (up to 10 jobs)
- Simple setup
- Runs in your app's environment

**Cons:**
- Limited to hourly/daily/10-minute intervals
- Not guaranteed exact timing (±30 minutes)

### Setup Steps

#### 1. Install Heroku Scheduler Add-on

```bash
heroku addons:create scheduler:standard --app your-app-name
```

#### 2. Open Scheduler Dashboard

```bash
heroku addons:open scheduler --app your-app-name
```

Or visit: https://dashboard.heroku.com/apps/your-app-name/scheduler

#### 3. Add Daily Job

In the Scheduler dashboard:
- Click "Add Job"
- Schedule: **Daily**
- Time: **8:00 AM** (or whenever you want)
- Run Command:
  ```bash
  python nba-props/scripts/daily_workflow.py
  ```

#### 4. That's It!

Your daily workflow will run automatically every day at 8 AM (in UTC timezone).

---

## Option 2: Heroku Dyno Worker (More Control)

If you need exact timing or want the job to run independently from your web server:

### 1. Create a `Procfile` Entry

Add to your `Procfile`:
```
web: gunicorn app:app
worker: python nba-props/scripts/scheduler.py
```

### 2. Create Scheduler Script

Create `nba-props/scripts/scheduler.py`:

```python
#!/usr/bin/env python3
"""
Heroku worker process for running daily NBA props workflow.
"""
import schedule
import time
import subprocess
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_daily_workflow():
    """Run the daily workflow script."""
    logger.info("Running daily NBA props workflow...")

    try:
        result = subprocess.run(
            ["python", "nba-props/scripts/daily_workflow.py"],
            capture_output=True,
            text=True,
            timeout=600  # 10 minute timeout
        )

        logger.info(f"Workflow exit code: {result.returncode}")
        if result.stdout:
            logger.info(f"STDOUT:\n{result.stdout}")
        if result.stderr:
            logger.error(f"STDERR:\n{result.stderr}")

    except Exception as e:
        logger.error(f"Error running workflow: {e}")

# Schedule the job
# Note: Times are in UTC on Heroku
schedule.every().day.at("13:00").do(run_daily_workflow)  # 8 AM EST = 1 PM UTC

logger.info("NBA Props scheduler started")
logger.info(f"Next run scheduled for: {schedule.next_run()}")

# Keep the worker running
while True:
    schedule.run_pending()
    time.sleep(60)  # Check every minute
```

### 3. Add Schedule Dependency

Add to `requirements.txt`:
```
schedule==1.2.0
```

### 4. Scale Up Worker Dyno

```bash
heroku ps:scale worker=1 --app your-app-name
```

**Cost:** Worker dynos cost $7/month (hobby tier) or $25/month (standard tier).

**Note:** You can scale it down when not needed:
```bash
heroku ps:scale worker=0 --app your-app-name
```

---

## Option 3: GitHub Actions (Free Alternative)

If you want to avoid Heroku costs entirely:

### 1. Create `.github/workflows/daily-nba-props.yml`

```yaml
name: Daily NBA Props Workflow

on:
  schedule:
    # Runs at 8 AM EST (1 PM UTC) every day
    - cron: '0 13 * * *'
  workflow_dispatch:  # Allows manual trigger

jobs:
  run-predictions:
    runs-on: ubuntu-latest

    steps:
    - name: Checkout code
      uses: actions/checkout@v3

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.12'

    - name: Install dependencies
      run: |
        cd nba-props
        pip install -r requirements.txt

    - name: Run daily workflow
      env:
        ODDS_API_KEY: ${{ secrets.ODDS_API_KEY }}
      run: |
        cd nba-props
        python scripts/daily_workflow.py

    - name: Commit and push results
      run: |
        git config --local user.email "action@github.com"
        git config --local user.name "GitHub Action"
        git add nba-props/exports/*.json
        git diff --quiet && git diff --staged --quiet || git commit -m "Update NBA props predictions [automated]"
        git push
```

### 2. Add Secrets to GitHub

1. Go to your repo → Settings → Secrets and variables → Actions
2. Add secret:
   - Name: `ODDS_API_KEY`
   - Value: Your Odds API key

**Pros:**
- Completely free
- Runs on GitHub's servers
- Commits results back to your repo

**Cons:**
- Exports are in your Git repo (not ideal for large files)
- Requires your database to be accessible (SQLite in repo or hosted database)

---

## Recommended Approach for Your Setup

Since you're already on Heroku with your web app:

### Best Option: Heroku Scheduler (Free)

1. **Add Heroku Scheduler** (free)
2. **Schedule daily job** for 8 AM
3. **Exports go to your Heroku filesystem**
4. **Web app reads from exports folder**

**Setup:**
```bash
# Add scheduler
heroku addons:create scheduler:standard --app your-app-name

# Open dashboard
heroku addons:open scheduler --app your-app-name

# Add job:
# - Daily at 8:00 AM
# - Command: python nba-props/scripts/daily_workflow.py
```

**Important Note:** Heroku's ephemeral filesystem means files reset on dyno restart. You have two options:

#### Option A: Use Database Only (Recommended)

Modify your web app to read predictions from the database instead of JSON files:

```python
# In nba_props/routes.py
@bp.route("/api/predictions")
@login_required
def api_predictions():
    from database import get_session, Prediction, Player, Game

    session = get_session()
    today = date.today()

    predictions = session.query(Prediction).join(Game).filter(
        Game.game_date == today
    ).all()

    # Format and return...
```

#### Option B: Use Cloud Storage (S3, Cloudinary, etc.)

Modify `_export_predictions()` to upload to S3:

```python
import boto3

def _export_predictions(self, predictions):
    # ... generate JSON ...

    # Upload to S3
    s3 = boto3.client('s3')
    s3.put_object(
        Bucket='your-bucket',
        Key='nba-props/plays.json',
        Body=json.dumps(simplified),
        ContentType='application/json'
    )
```

---

## Testing Your Automation

### Test Locally First

```bash
python nba-props/scripts/daily_workflow.py
```

### Test on Heroku

```bash
# Run one-off command
heroku run python nba-props/scripts/daily_workflow.py --app your-app-name

# Check logs
heroku logs --tail --app your-app-name
```

### Verify Scheduler

```bash
# View scheduled jobs
heroku addons:open scheduler --app your-app-name

# Check worker logs (if using worker dyno)
heroku logs --tail --dyno worker --app your-app-name
```

---

## Monitoring & Alerts

### Option 1: Heroku Logging

```bash
# View recent logs
heroku logs --tail --app your-app-name

# Filter for NBA props logs
heroku logs --tail --app your-app-name | grep "NBA PROPS"
```

### Option 2: Log Drains (Papertrail, Loggly)

Add a log management service:

```bash
# Example: Papertrail (free tier)
heroku addons:create papertrail:choklad --app your-app-name
heroku addons:open papertrail --app your-app-name
```

Set up alerts for:
- "Workflow failed"
- "Model not found"
- "API requests remaining: 0"

---

## Cost Breakdown

### Free Option
- **Heroku Scheduler:** Free (10 jobs max)
- **Web Dyno:** Free (hobby tier, sleeps after 30 min)
- **Total:** $0/month

### Paid Option (Always-On)
- **Heroku Scheduler:** Free
- **Web Dyno:** $7/month (hobby tier, always on)
- **Worker Dyno (optional):** $7/month
- **Total:** $7-14/month

### Recommended for You
Start with **free tier + Heroku Scheduler**, then upgrade to hobby dyno ($7/month) when you want 24/7 uptime.

---

## Troubleshooting

### Job Not Running

1. **Check Heroku Scheduler logs:**
   ```bash
   heroku logs --tail --app your-app-name | grep scheduler
   ```

2. **Verify timezone:**
   - Heroku uses UTC
   - 8 AM EST = 1 PM UTC
   - Adjust schedule accordingly

3. **Test manually:**
   ```bash
   heroku run python nba-props/scripts/daily_workflow.py --app your-app-name
   ```

### Files Not Persisting

**Problem:** Heroku's filesystem is ephemeral (resets on restart)

**Solutions:**
1. Read from database instead of JSON files
2. Use cloud storage (S3, Google Cloud Storage)
3. Use Heroku Postgres + store JSON in database

### API Key Not Found

Add environment variable to Heroku:

```bash
heroku config:set ODDS_API_KEY=your-key-here --app your-app-name
```

---

## Summary

**For your setup, I recommend:**

1. ✅ **Heroku Scheduler** - Free, simple, works with your existing app
2. ✅ **Read from database** - Avoids ephemeral filesystem issues
3. ✅ **Monitor with Papertrail** - Free log management and alerts

**Setup Commands:**
```bash
# Add scheduler
heroku addons:create scheduler:standard --app your-app-name

# Set API key
heroku config:set ODDS_API_KEY=your-key --app your-app-name

# Add job in dashboard
heroku addons:open scheduler --app your-app-name
# Job: python nba-props/scripts/daily_workflow.py
# Frequency: Daily at 13:00 (8 AM EST)
```

Done! Your predictions will update automatically every day. 🎉
