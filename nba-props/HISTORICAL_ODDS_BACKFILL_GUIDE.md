# Historical Odds Backfill Guide

## Overview

Now that you have The Odds API Pro plan, you can backfill historical prop odds data to:
1. Train better ML models that learn Vegas line-setting behavior
2. Detect anomalies and deviations in current prop lines
3. Identify "sharp movements" (Vegas traps)
4. Build historical baselines for each player's typical lines

## Quick Start

```bash
# Test with a few games first
python scripts/backfill_historical_odds.py --season 2025-26 --limit 5

# If successful, run full backfill
python scripts/backfill_historical_odds.py --season 2025-26
```

## Important Limitations

### 1. Historical Data Availability

**The Odds API historical data typically only goes back 30-90 days.**

- If your games are older than 90 days, the API may not have data
- Early season games (October 2025) might not have historical odds available if it's now mid-November
- The script will skip games without available historical data

### 2. API Credit Usage

**Each game requires 7 API requests** (one per prop market):
- player_points
- player_rebounds
- player_assists
- player_threes
- player_blocks
- player_steals
- player_turnovers

**Estimating costs:**
```
Games completed this season: ~200 (as of mid-November)
Requests per game: 7
Total requests: ~1,400

Your monthly limit: 20,000 requests
Remaining after backfill: ~18,600 requests
```

You have plenty of room!

### 3. Matching Players

The script matches player names from The Odds API to your database:
- Tries exact name match first
- Falls back to last name match
- Some players may not match (logged as warnings)

## Running the Backfill

### Option 1: Test with Limited Games

Start small to verify everything works:

```bash
python scripts/backfill_historical_odds.py --season 2025-26 --limit 5 --delay 2.0
```

This will:
- Process only 5 games
- Wait 2 seconds between games (gentle on the API)
- Show you what data is available

**Check the output:**
- Look for "Added X props" messages
- If you see many "No historical data returned" warnings, the games may be too old

### Option 2: Full Season Backfill

Once you confirm it's working:

```bash
python scripts/backfill_historical_odds.py --season 2025-26 --delay 1.0
```

This will:
- Process ALL completed games from 2025-26 season
- Wait 1 second between games
- Take approximately 3-5 minutes to complete

**Expected output:**
```
Found 200 completed games to backfill
[1/200] Processing game: Lakers vs Warriors on 2025-10-22
  Fetching odds from around 2025-10-22 12:00
    Added 120 player_points props
    Added 85 player_rebounds props
    Added 92 player_assists props
    ...
[2/200] Processing game: Celtics vs Heat on 2025-10-23
  Already have 856 props for this game, skipping...
...

BACKFILL COMPLETE
Games processed: 200
Props added: 45,320
API requests made: 1,400
```

## What Happens Next

### 1. Database is Populated

Your `nba_prop_lines` table now has historical prop lines with:
- Player ID
- Game ID
- Prop type (points, rebounds, etc.)
- Line value (the over/under number)
- Over/under odds
- Sportsbook name
- Timestamp when fetched

### 2. Deviation Detection Features Activate

The `FeatureCalculator` already has code to detect deviations:

```python
# These features are now calculated!
features['line_vs_avg']      # How much current line differs from historical avg
features['line_vs_recent']   # How much current line differs from last 5 games
features['sharp_movement']   # How much line moved recently
features['is_sharp_movement'] # 1 if moved >2.5 points (potential trap)
```

### 3. Train Full ML Model

Now you can train the classification model (not just regression):

```bash
# Train model that predicts over/under with line movement patterns
python scripts/train_model.py --prop-type points
```

This model will:
- Learn when Vegas sets unusual lines
- Detect when lines deviate from player's typical values
- Identify sharp movements and traps
- Expected accuracy: 55-58% (vs 54% for stats-only model)

### 4. Generate Better Predictions

```bash
# Get predictions with anomaly detection
python scripts/generate_predictions.py --prop-type points --min-confidence 0.65
```

The predictions will now include:
- "This line is 3.5 points higher than this player's typical line"
- "Sharp movement detected - line moved 4 points in last 24 hours"
- Flags for unusual lines that may be Vegas traps

## Troubleshooting

### "No historical data returned"

**Cause:** The Odds API doesn't have data for that date (too old)

**Solution:**
- Historical data typically only goes back 30-90 days
- Games from October may not have data if it's now mid-November
- This is okay - the script will skip those games

### "Player not found: LeBron James"

**Cause:** Player name from Odds API doesn't match database

**Solutions:**
- Check if player is in your database: `python scripts/query_data.py player "LeBron"`
- The script tries fuzzy matching, so minor differences are okay
- Very rare - most players match automatically

### "API request failed: 401 Unauthorized"

**Cause:** API key issue

**Solution:**
- Verify your API key in `.env` file
- Make sure your Pro plan is active
- Check your usage at the-odds-api.com

### "API request failed: 429 Too Many Requests"

**Cause:** Rate limiting

**Solution:**
- Increase delay: `--delay 2.0` or higher
- The Odds API has rate limits even for Pro plans
- Wait a few minutes and resume

## Verifying the Backfill

After running, check your database:

```bash
python scripts/query_data.py stats
```

Look for:
```
Prop Lines: 45,000+  # Should see a big number!
```

Or check specific player:

```python
from database import get_session, PropLine, Player
session = get_session()

# Get LeBron's historical lines
lebron = session.query(Player).filter_by(full_name="LeBron James").first()
lines = session.query(PropLine).filter(
    PropLine.player_id == lebron.id,
    PropLine.prop_type == 'points'
).all()

print(f"LeBron has {len(lines)} historical point lines")
for line in lines[:5]:
    print(f"  {line.line_value} points on {line.fetched_at.date()}")
```

## Next Steps

1. **Verify backfill worked:**
   ```bash
   python scripts/query_data.py stats
   ```

2. **Train full classification model:**
   ```bash
   python scripts/train_model.py --prop-type points
   ```

3. **Compare models:**
   - Your current regression model: 57.1% simulated accuracy
   - New classification model with odds: Expected 56-58% real accuracy

4. **Generate predictions with anomaly detection:**
   ```bash
   python scripts/generate_predictions.py --prop-type points --min-confidence 0.65
   ```

## Cost Tracking

Monitor your API usage:
- The script shows "API requests made: X" at the end
- Your Pro plan: 20,000 requests/month
- Resets on the 1st of each month

**Typical usage:**
- Historical backfill (one-time): ~1,400 requests
- Daily collection: ~10-20 requests/day
- Monthly total: ~1,400 + (20 × 30) = ~2,000 requests/month

**You're well within limits!**

## When to Re-run

You typically only need to run this once. But re-run if:
1. You add new completed games to your database
2. You want to refresh lines (sportsbooks sometimes adjust after games start)
3. Your database was reset

The script automatically skips games that already have odds, so it's safe to re-run.

## Questions?

- Check CHEATSHEET.md for command reference
- Check HISTORICAL_ODDS_GUIDE.md for background on why historical odds matter
- The script is well-commented - read the code for details!
