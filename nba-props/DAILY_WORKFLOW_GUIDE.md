# Daily Workflow & Website Integration Guide

## Overview

This guide shows you:
1. **How the system works now**
2. **What to run daily** (one simple command!)
3. **How to integrate predictions into your website**
4. **Weekly maintenance tasks**

---

## Current System Status

### What's Working:
- ✓ Database initialized with teams and players
- ✓ Historical game data collected (2025-26 season)
- ✓ Regression model trained (57.1% simulated accuracy)
- ✓ Daily prop collection working (9,381 props collected)
- ✓ Prediction generation working (304 predictions generated)

### What You Have:
- **Regression Model**: Predicts actual stat values (e.g., "LeBron will score 26.3 points")
- **Daily Collection**: Fetches current betting lines from The Odds API
- **Prediction System**: Compares model predictions to betting lines to find edges

### How It Works:
1. **Model looks at**: Player's last 10 games, opponent defense, home/away, minutes played, etc.
2. **Compares to**: Current betting line (e.g., LeBron O/U 24.5 points)
3. **Finds edge**: If model predicts 28 points and line is 24.5, that's a +3.5 edge = OVER play

---

## Daily Workflow (ONE COMMAND)

### Run This Every Morning:

```bash
cd C:\Users\arhic\PycharmProjects\pollCLAAMP\nba-props
python scripts/daily_workflow.py
```

### What This Does:
1. ✓ Collects today's prop lines from The Odds API
2. ✓ Generates predictions using your trained model
3. ✓ Stores predictions in database
4. ✓ **Exports predictions to JSON files** (for your website!)
5. ✓ Shows you the top 10 best plays

### Example Output:
```
============================================================
NBA PROPS - DAILY WORKFLOW
============================================================
Started: 2025-11-17 09:00:00

[1/3] Collecting today's prop lines...
      Collected 9,234 prop lines

[2/3] Generating predictions...
      Generated 286 predictions

[3/3] Exporting predictions for website...
      Exported to: C:\Users\arhic\PycharmProjects\pollCLAAMP\nba-props\exports\predictions.json

============================================================
DAILY WORKFLOW COMPLETE!
============================================================
Prop lines collected: 9,234
Predictions generated: 286
API requests used: ~15

TOP PREDICTIONS (Highest Confidence):
------------------------------------------------------------
LeBron James              points   Line:  24.5  Pred:  28.3  OVER     (Edge: +3.8)
Stephen Curry             threes   Line:   4.5  Pred:   6.2  OVER     (Edge: +1.7)
...
```

---

## Files Generated (For Your Website)

After running the daily workflow, you'll have these files:

### 1. `exports/plays.json` (Simplified - Best for Website)
```json
{
  "updated": "2025-11-17T09:00:00Z",
  "count": 125,
  "plays": [
    {
      "player": "LeBron James",
      "stat": "points",
      "line": 24.5,
      "prediction": 28.3,
      "play": "OVER",
      "edge": 3.8,
      "game": "Lakers vs Warriors",
      "time": "7:00 PM PT"
    },
    ...
  ]
}
```

### 2. `exports/predictions.json` (Full Data)
Contains all predictions including "NO PLAY" recommendations with full details.

---

## Website Integration Options

You have **3 options** to integrate predictions into your website:

### Option 1: Read JSON File Directly (Simplest)

Your Node.js/Express server can just read the JSON file:

```javascript
// In your web server (pollCLAAMP/server.js or similar)
const fs = require('fs');
const path = require('path');

app.get('/api/nba-props', (req, res) => {
  try {
    const playsPath = path.join(__dirname, 'nba-props', 'exports', 'plays.json');
    const plays = JSON.parse(fs.readFileSync(playsPath, 'utf8'));
    res.json(plays);
  } catch (error) {
    res.status(500).json({ error: 'No predictions available' });
  }
});
```

**Pros**: Super simple, no additional setup
**Cons**: File must exist before server reads it

### Option 2: API Endpoint (Recommended)

Run the predictions API server alongside your main server:

```bash
# Terminal 1: Your main web server
npm start

# Terminal 2: NBA Props API
python nba-props/api/predictions_api.py
```

Then your frontend can fetch from: `http://localhost:5001/api/predictions/export`

**Example frontend code:**
```javascript
// In your React/Vue/etc component
fetch('http://localhost:5001/api/predictions/export')
  .then(res => res.json())
  .then(data => {
    console.log('Today\'s plays:', data.plays);
    // Display on your website
  });
```

**Pros**: Real-time data, query parameters, stats endpoints
**Cons**: Need to run two servers

### Option 3: Shared Database

Your web server can query the same SQLite database:

```javascript
// In your Node.js server
const sqlite3 = require('sqlite3');
const db = new sqlite3.Database('./nba-props/nba_props.db');

app.get('/api/predictions', (req, res) => {
  db.all(`
    SELECT p.*, pl.full_name as player_name
    FROM nba_predictions p
    JOIN nba_players pl ON p.player_id = pl.id
    WHERE DATE(p.created_at) = DATE('now')
    ORDER BY ABS(p.predicted_value - p.line_value) DESC
    LIMIT 50
  `, (err, rows) => {
    if (err) return res.status(500).json({ error: err.message });
    res.json({ predictions: rows });
  });
});
```

**Pros**: Direct database access, most flexible
**Cons**: Need to install sqlite3 package for Node.js

---

## Recommended Setup for You

Based on your setup, I recommend **Option 1 (JSON file)** to start:

### 1. Install Flask (for API server if you want it later):
```bash
pip install -r nba-props/requirements.txt
```

### 2. Daily Routine:
```bash
# Morning: Run workflow (takes ~30 seconds)
python nba-props/scripts/daily_workflow.py
```

### 3. Add to Your Web Server:

Create an endpoint in your web server that reads the JSON:

```javascript
// pollCLAAMP/routes/nba.js (or wherever you want)
const express = require('express');
const fs = require('fs');
const path = require('path');
const router = express.Router();

router.get('/predictions', (req, res) => {
  try {
    const playsPath = path.join(__dirname, '..', 'nba-props', 'exports', 'plays.json');

    if (!fs.existsSync(playsPath)) {
      return res.status(404).json({
        error: 'No predictions available yet. Run daily workflow first.'
      });
    }

    const plays = JSON.parse(fs.readFileSync(playsPath, 'utf8'));
    res.json(plays);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

module.exports = router;
```

### 4. Create Frontend Display:

```jsx
// Example React component
function NBAPropsDisplay() {
  const [plays, setPlays] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/nba/predictions')
      .then(res => res.json())
      .then(data => {
        setPlays(data.plays);
        setLoading(false);
      });
  }, []);

  if (loading) return <div>Loading predictions...</div>;

  return (
    <div className="nba-props">
      <h2>Today's NBA Props ({plays.length} plays)</h2>
      <p>Updated: {new Date(plays[0]?.updated).toLocaleString()}</p>

      <table>
        <thead>
          <tr>
            <th>Player</th>
            <th>Stat</th>
            <th>Line</th>
            <th>Prediction</th>
            <th>Play</th>
            <th>Edge</th>
          </tr>
        </thead>
        <tbody>
          {plays.map((play, idx) => (
            <tr key={idx}>
              <td>{play.player}</td>
              <td>{play.stat}</td>
              <td>{play.line}</td>
              <td>{play.prediction.toFixed(1)}</td>
              <td className={play.play === 'OVER' ? 'over' : 'under'}>
                {play.play}
              </td>
              <td>{play.edge > 0 ? '+' : ''}{play.edge.toFixed(1)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

---

## Weekly Maintenance

### Every Sunday (or when you have time):

```bash
# Retrain the model with latest data
python nba-props/scripts/train_model_no_odds.py --prop-type points
```

**Why?**
- The model learns from new games each week
- Player performance changes (injuries, hot streaks, etc.)
- Expected improvement: 57% → 58%+ accuracy over time

### Every Month:

```bash
# Check model accuracy
python nba-props/scripts/query_data.py stats
```

Look for:
- Total predictions made
- Accuracy percentage (if you're tracking results)

---

## Tracking Results (Optional but Recommended)

To see how well your model is doing, track your predictions:

```bash
# After games finish, mark results
python nba-props/scripts/track_results.py
```

This will:
- Check if your predictions were correct
- Calculate accuracy percentage
- Show you ROI (if you bet $100 per play)
- Help improve the model over time

---

## Automation (Optional)

### Windows Task Scheduler:

Create a scheduled task to run the daily workflow automatically:

1. Open **Task Scheduler**
2. Create Basic Task → "NBA Props Daily Workflow"
3. Trigger: Daily at 8:00 AM
4. Action: Start a Program
   - Program: `C:\Users\arhic\AppData\Local\Programs\Python\Python312\python.exe`
   - Arguments: `C:\Users\arhic\PycharmProjects\pollCLAAMP\nba-props\scripts\daily_workflow.py`
5. Done!

Now it runs automatically every morning!

---

## Troubleshooting

### "Model not found" error:
```bash
# Train the model first
python nba-props/scripts/train_model_no_odds.py --prop-type points
```

### "No props collected" warning:
- Check if there are games today (NBA doesn't play every day)
- Verify your Odds API key in `.env` file
- Check API usage: You have 20,000 requests/month

### "exports/plays.json not found":
- Run the daily workflow at least once
- The file is created automatically when you run `daily_workflow.py`

---

## Summary: Your Daily Routine

### Morning (5 minutes):
```bash
1. cd C:\Users\arhic\PycharmProjects\pollCLAAMP\nba-props
2. python scripts/daily_workflow.py
3. Check exports/plays.json exists
4. Your website now shows today's predictions!
```

### Weekly (10 minutes):
```bash
# Retrain model
python scripts/train_model_no_odds.py --prop-type points
```

### That's It!

Your predictions will be:
- ✓ Fresh every day
- ✓ Based on latest stats
- ✓ Available on your website
- ✓ Automatically updated

---

## Questions?

- **How accurate is the model?** ~57% simulated accuracy (better than 50/50!)
- **How many API requests per day?** ~15-20 (you have 20,000/month)
- **Can I run this for multiple prop types?** Yes! Just train models for rebounds, assists, etc.
- **Do I need historical odds?** No! The regression model works without historical odds data.

---

## Next Steps

1. **Test the workflow:**
   ```bash
   python nba-props/scripts/daily_workflow.py
   ```

2. **Check the exports:**
   ```bash
   # On Windows:
   type nba-props\exports\plays.json
   ```

3. **Add to your website:**
   - Create API endpoint to read plays.json
   - Build frontend component to display predictions
   - Deploy!

4. **Automate:**
   - Set up Windows Task Scheduler
   - Runs automatically every morning
   - No manual work needed!

---

Ready to make some money? 💰
