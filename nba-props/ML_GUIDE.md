# NBA Props Machine Learning Guide

Complete guide to training and using ML models for NBA player props predictions.

## Overview

This ML system predicts whether player props (points, rebounds, assists, etc.) will go **OVER** or **UNDER** the betting line. It uses:

- **XGBoost** - Gradient boosting algorithm (excellent for tabular data)
- **50+ features** - Player stats, trends, streaks, line movements, etc.
- **Smart detection** - Catches Vegas traps (sharp line movements)
- **Backtesting** - Measure profitability on historical data

---

## Quick Start

### 1. Install ML Dependencies

```bash
pip install xgboost scikit-learn
```

### 2. Collect Historical Data

You need historical game data and prop lines to train the model:

```bash
# Backfill last season's data
python scripts/backfill_historical.py --season 2024-25

# Collect recent prop lines (run daily for a few weeks)
python scripts/collect_daily_data.py
```

**Minimum data needed:** ~100 games with prop lines (about 2-3 weeks of daily collection)

### 3. Train the Model

```bash
# Train on points props (most common)
python scripts/train_model.py --prop-type points

# Train on other prop types
python scripts/train_model.py --prop-type rebounds
python scripts/train_model.py --prop-type assists
```

This will:
- Prepare training data from your database
- Train an XGBoost model
- Show performance metrics
- Save model to `models/points_model.pkl`

### 4. Generate Predictions

```bash
# Generate predictions for today's games
python scripts/generate_predictions.py --prop-type points --min-confidence 0.60

# Save predictions to database
python scripts/generate_predictions.py --prop-type points --save-to-db
```

### 5. Backtest Performance

```bash
# Test on last 30 days
python scripts/backtest_model.py --prop-type points --days-back 30

# Custom parameters
python scripts/backtest_model.py --prop-type points --days-back 60 --min-confidence 0.65 --unit-size 100
```

---

## Features Explained

The model uses **50+ features** across several categories:

### 1. Rolling Averages (Performance Trends)
- `points_avg_last_3/5/10/15` - Recent averages over different windows
- `points_std_last_X` - Consistency/volatility
- `points_max_last_X` / `points_min_last_X` - Range
- `points_median_last_X` - Median performance

### 2. Trend Features (Momentum)
- `points_trend_last_10` - Is performance improving or declining?
- `points_momentum` - Last 3 games vs previous 3 games
- `points_consistency` - Coefficient of variation (lower = more consistent)
- `points_games_over_avg_last_5` - How many recent games exceeded season average

### 3. Home/Away Splits
- `points_home_avg` / `points_away_avg` - Performance by location
- `points_home_away_diff` - Home court advantage/disadvantage

### 4. Streak Features (KEY for catching trends!)
- `over_streak` - Consecutive games hitting OVER
- `under_streak` - Consecutive games hitting UNDER
- `hit_rate_last_5/10` - What % of recent games went over the line
- `line_change_after_streak` - How Vegas adjusted the line

### 5. Line Movement Features (Vegas Trap Detection!)
- `line_vs_avg` - Current line vs historical average
- `line_vs_recent` - Current line vs recent average
- `line_std` - Line volatility
- `line_movement` - Change from last game
- `sharp_movement` - **BIG LINE MOVE** (2.5+ points)
- `is_sharp_movement` - Binary flag for sharp moves

### 6. Minutes/Playing Time
- `minutes_avg` - Average playing time
- `minutes_trend` - Is playing time increasing/decreasing?
- `minutes_consistency` - How stable is playing time?

### 7. Context Features
- `days_rest` - Days between games (back-to-back vs rested)

---

## Understanding the Output

### Training Output Example

```
MODEL PERFORMANCE
============================================================

Training Accuracy: 0.6234
Training AUC: 0.6891

Test Accuracy: 0.5847
Test AUC: 0.6245

Test Set Classification Report:
              precision    recall  f1-score   support

       Under       0.57      0.62      0.59       245
        Over       0.60      0.55      0.57       255

Top 20 Most Important Features:
              feature  importance
    points_avg_last_10    0.1234
           over_streak    0.0987
      sharp_movement    0.0856
    hit_rate_last_5    0.0723
```

**Key Metrics:**
- **Accuracy >54%** = Profitable (break-even at -110 odds is 52.38%)
- **AUC >0.60** = Model has predictive power
- **Feature Importance** = Which features matter most

### Prediction Output Example

```
PREDICTIONS FOR POINTS - 2024-11-15
============================================================

Found 12 recommended plays (min confidence: 60%)

HIGH CONFIDENCE PLAYS (3 plays)
------------------------------------------------------------

LeBron James            | OVER   25.5
  Confidence: 72.3% | Predicted: 28.1 | Edge: +2.6
  Last 10 Avg: 27.8 | Minutes: 34.2
  Streak: 5 consecutive OVERS
  Hit Rate (last 5): 100.0%
  Sportsbook: draftkings

Anthony Davis           | UNDER  27.5
  Confidence: 68.9% | Predicted: 23.4 | Edge: -4.1
  Last 10 Avg: 24.1 | Minutes: 32.8
  Hit Rate (last 5): 20.0%
  [!] SHARP LINE MOVEMENT: 3.5 point move - Vegas Trap?
  Sportsbook: fanduel
```

**What it means:**
- **Confidence** - Model's certainty (higher = stronger pick)
- **Predicted** - What the model thinks the player will score
- **Edge** - Difference from betting line (predicted - line)
- **Streak** - Hot/cold streaks
- **Sharp Movement** - Vegas adjusted line sharply (could be a trap!)

### Backtesting Output Example

```
BACKTEST RESULTS
============================================================

Overall Performance:
  Total Bets: 147
  Wins: 84 (57.1%)
  Losses: 63
  Total Profit: $612.45
  Average Profit/Bet: $4.17
  ROI: 4.17%

  Break-even win rate at -110 odds: 52.38%
  [OK] You are profitable! (57.1% > 52.38%)

Performance by Confidence Level:
  60-65%: 45 bets, 52.2% win rate, -$89.09 profit, -1.98% ROI
  65-70%: 58 bets, 56.9% win rate, $234.78 profit, 4.05% ROI
  70-75%: 32 bets, 62.5% win rate, $356.25 profit, 11.13% ROI
  75%+: 12 bets, 66.7% win rate, $110.51 profit, 9.21% ROI

Sharp Line Movement Bets (Vegas Traps):
  Total bets: 23
  Win rate: 43.5%
  Profit: -$178.26
  [!] Sharp movements are losing - model catching Vegas traps well!
```

---

## How It Works: The Strategy

### 1. Capturing Trends

**Example:** LeBron hits the OVER 5 games in a row
- Vegas raises his line from 24.5 → 27.5 (sharp movement)
- Public sees high line and bets UNDER
- **Model knows:** LeBron is hot, still take OVER despite high line

**Features that catch this:**
- `over_streak = 5`
- `sharp_movement = 3.0`
- `hit_rate_last_5 = 1.0` (100%)
- `line_movement = +3.0`

### 2. Catching Vegas Traps

**Example:** Player averages 22 points, line suddenly drops to 18.5
- Sharp 3.5 point drop (Vegas knows something)
- Public thinks it's easy OVER
- **Model knows:** Sharp movement = trap, bet UNDER

**Features that catch this:**
- `is_sharp_movement = 1`
- `line_vs_recent = -3.5`
- Historical performance shows sharp moves often lose

### 3. Minutes Consistency

**Example:** Player's minutes dropping (33 → 30 → 28 last 3 games)
- Line hasn't adjusted yet
- **Model knows:** Less playing time = harder to hit OVER

**Features:**
- `minutes_trend = -2.5`
- `minutes_consistency = low`

### 4. Home/Away Splits

**Example:** Player averages 25 at home, 19 on road
- Tonight is away game, line is 23.5
- **Model knows:** Take UNDER based on road performance

**Features:**
- `points_home_avg = 25.0`
- `points_away_avg = 19.0`
- `points_home_away_diff = -6.0`

---

## Workflow

### Daily Routine

```bash
# Morning (before games start)
# 1. Collect today's props
python scripts/collect_daily_data.py

# 2. Generate predictions
python scripts/generate_predictions.py --prop-type points --min-confidence 0.65

# 3. Review recommendations and place bets

# Evening (after games complete)
# 4. Update game results
python scripts/collect_daily_data.py --update-completed
```

### Weekly Maintenance

```bash
# 1. Retrain model with new data
python scripts/train_model.py --prop-type points

# 2. Backtest to check performance
python scripts/backtest_model.py --prop-type points --days-back 30

# 3. If performance degrades, investigate:
#    - Is data collection working?
#    - Did Vegas change strategies?
#    - Need more features?
```

---

## Tips for Best Results

### 1. Start Conservative
- Use `--min-confidence 0.65` or higher at first
- Only bet on HIGH CONFIDENCE plays
- Track your results manually

### 2. Bankroll Management
- **Never bet more than 1-2% of bankroll per pick**
- Even at 57% win rate, you'll have losing streaks
- Unit size = 1% of bankroll is safe

### 3. Avoid Common Mistakes
- ❌ Don't bet every prediction (wait for high confidence)
- ❌ Don't chase losses by increasing bet size
- ❌ Don't ignore sharp movement warnings
- ✅ Do track all bets in a spreadsheet
- ✅ Do review what features led to wins/losses
- ✅ Do retrain model weekly with new data

### 4. When to Trust the Model
- ✅ High confidence (70%+)
- ✅ Multiple features align (streak + trend + edge)
- ✅ Minutes are consistent
- ✅ Model catches a pattern you missed

### 5. When to Be Cautious
- ⚠️ Sharp line movement flagged
- ⚠️ Player coming back from injury
- ⚠️ Model confidence just barely above threshold
- ⚠️ Minutes trend is inconsistent

---

## Advanced: Feature Engineering

Want to add your own features? Edit `services/feature_calculator.py`:

```python
def calculate_custom_features(self, ...):
    features = {}

    # Example: Opponent defensive rating
    opponent_def_rating = get_opponent_defense()
    features['opponent_def_rating'] = opponent_def_rating

    # Example: Days since last 30+ point game
    last_big_game = find_last_game_over_30()
    features['days_since_big_game'] = (today - last_big_game).days

    return features
```

Then retrain the model to include new features.

---

## Troubleshooting

### "Not enough training data"
- Collect more data (run `collect_daily_data.py` for 2-3 weeks)
- Or use `--days-back` with a longer period (if you have historical data)

### "Model not found"
- Run `train_model.py` first
- Check that `models/points_model.pkl` exists

### "Low accuracy (<54%)"
- Need more data (especially prop lines)
- Try different `--min-confidence` threshold
- Some props are harder to predict (try points first, then rebounds/assists)

### "Model says OVER, player scores way under"
- Check the game log - was there an injury?
- Check minutes played - did coach sit them early?
- This is variance - happens even with good models

---

## Expected Performance

Realistic expectations based on NBA props betting:

- **Win Rate:** 54-58% (52.38% breaks even at -110 odds)
- **ROI:** 2-6% (excellent for sports betting)
- **Confidence 70%+ plays:** 60-65% win rate
- **Sharp movement plays:** 45-50% win rate (Vegas wins these!)

**Don't expect:**
- ❌ 70% win rate overall (impossible long-term)
- ❌ Winning every high confidence play
- ❌ Never hitting losing streaks

**Do expect:**
- ✅ Slight edge over Vegas (54-58% vs 50%)
- ✅ Better performance on high confidence plays
- ✅ Profit over large sample sizes (100+ bets)

---

## Files Created

```
nba-props/
├── services/
│   └── feature_calculator.py     # Feature engineering logic
├── scripts/
│   ├── train_model.py            # Train XGBoost model
│   ├── generate_predictions.py   # Daily predictions
│   └── backtest_model.py         # Test on historical data
└── models/                        # Saved models (created on first train)
    ├── points_model.pkl
    ├── points_features.pkl
    ├── rebounds_model.pkl
    └── ...
```

---

## Next Steps

1. **Collect Data** - Run daily collection for 2-3 weeks
2. **Train Model** - Once you have ~100 props with results
3. **Backtest** - Verify profitability on historical data
4. **Start Small** - Bet small amounts on high confidence plays
5. **Track Results** - Keep a spreadsheet of all bets
6. **Iterate** - Retrain weekly, adjust confidence thresholds

---

**Good luck and bet responsibly! 🏀📈**
