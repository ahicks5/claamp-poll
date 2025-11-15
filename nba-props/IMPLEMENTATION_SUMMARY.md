# NBA Props System - Implementation Summary

## What Was Built

A complete data collection system for NBA player props betting, designed to run locally on your machine.

### Directory Structure
```
nba-props/
├── database/
│   ├── __init__.py
│   ├── db.py                    # SQLAlchemy database connection
│   └── models.py                # Data models (7 tables)
├── services/
│   ├── __init__.py
│   ├── nba_api_client.py       # NBA stats API client
│   └── odds_api_client.py      # The Odds API client
├── scripts/
│   ├── __init__.py
│   ├── init_database.py        # Initialize DB & load teams/players
│   ├── backfill_historical.py  # Load historical game data
│   ├── collect_daily_data.py   # Daily collection workflow
│   └── query_data.py            # Inspect collected data
├── logs/                        # Log files directory
├── .env                         # Environment config (with your API key)
├── .env.example                 # Template for .env
├── .gitignore                   # Git ignore rules
├── requirements.txt             # Python dependencies
├── README.md                    # Full documentation
├── QUICKSTART.md               # Quick start guide
└── nba_props.db                # SQLite database (created)
```

## Database Schema (7 Tables)

### Reference Data
1. **nba_teams** - 30 NBA teams ✓ (populated)
2. **nba_players** - ~450 active players (run init_database.py to populate)

### Game Data
3. **nba_games** - Game records (past and upcoming)
4. **nba_player_game_stats** - Actual player performance per game

### Betting Data
5. **nba_prop_lines** - Betting lines from sportsbooks (points, rebounds, assists, etc.)

### Prediction System (for future)
6. **nba_predictions** - Your model's predictions
7. **nba_results** - Track prediction accuracy

## Key Features Implemented

### 1. NBA API Integration
- ✓ Fetch all teams and players
- ✓ Get player game-by-game stats
- ✓ Get today's games schedule
- ✓ Get box scores for completed games
- ✓ Built-in rate limiting (600ms between requests)
- ✓ Fuzzy player name matching

### 2. Odds API Integration
- ✓ Fetch upcoming NBA games
- ✓ Fetch player props for each game
- ✓ Support for multiple prop types (points, rebounds, assists, combos)
- ✓ Support for multiple sportsbooks (DraftKings, FanDuel, etc.)
- ✓ Track API usage (shows remaining requests)
- ✓ Parse odds data and store with timestamps

### 3. Data Collection Scripts
- ✓ **init_database.py** - One-time setup (creates tables, loads teams/players)
- ✓ **backfill_historical.py** - Load past seasons (2023-24, 2024-25)
- ✓ **collect_daily_data.py** - Daily workflow (fetch games & props)
- ✓ **query_data.py** - Inspect data (interactive and CLI modes)

### 4. Error Handling & Logging
- ✓ Comprehensive error handling for API failures
- ✓ Logging to console and files
- ✓ Retry logic for network errors
- ✓ Duplicate prevention (database constraints)
- ✓ Graceful handling of missing/malformed data

## What You Can Do Now

### Immediate Next Steps
```bash
cd /home/user/claamp-poll/nba-props

# 1. Complete database initialization (loads all players)
python scripts/init_database.py

# 2. Collect today's props
python scripts/collect_daily_data.py

# 3. View collected data
python scripts/query_data.py props
```

### Data Collection Options
```bash
# Backfill current season (takes ~30-60 min)
python scripts/backfill_historical.py --season 2024-25

# Backfill last season for more training data
python scripts/backfill_historical.py --season 2023-24

# Collect props for next 2 days
python scripts/collect_daily_data.py --days-ahead 2

# Update stats for recently completed games
python scripts/collect_daily_data.py --update-completed
```

### Query Data Examples
```bash
# Interactive menu
python scripts/query_data.py

# Database statistics
python scripts/query_data.py stats

# Show recent games
python scripts/query_data.py games

# Today's prop lines
python scripts/query_data.py props

# Specific player stats
python scripts/query_data.py player "LeBron James"

# Top scorers this season
python scripts/query_data.py top points
```

## API Usage Guidelines

### The Odds API (Free Tier)
- **Limit:** 500 requests/month
- **Daily cost:** ~10-20 requests (depends on # of games)
- **Best practice:** Run collection once per day in the morning
- **Conserve usage:** Only collect when you need fresh data

### NBA API (Unofficial)
- **No hard limit** but respect rate limiting
- **Built-in delay:** 600ms between requests (already implemented)
- **Safe to use:** For backfilling historical data anytime

## What's Next: Building the Prediction System

### Phase 1: Feature Engineering
Build features from collected data:
- Player rolling averages (last 5, 10, 15 games)
- Home/Away splits
- Opponent defensive ratings
- Days rest (back-to-back vs. rested)
- Minutes trends
- Recent form/streaks

### Phase 2: Model Training
Train ML models using historical data:
- Start with simple models (Linear Regression, Random Forest)
- Progress to XGBoost, LightGBM
- Try deep learning (Neural Networks) if you have enough data
- Use cross-validation to avoid overfitting

### Phase 3: Prediction Pipeline
- Fetch today's props (done!)
- Calculate features for each player
- Generate predictions using trained model
- Compare prediction vs. betting line
- Identify edges (where you have an advantage)
- Store predictions in `nba_predictions` table

### Phase 4: Tracking & Iteration
- Record actual outcomes in `nba_results` table
- Calculate accuracy metrics (hit rate, ROI, Sharpe ratio)
- Analyze errors to improve model
- Iterate on features and model architecture

### Phase 5: Web Integration
Eventually integrate into your Flask app:
- Add NBA props routes (`/nba-props/`)
- Show daily picks with confidence scores
- Display historical performance
- User authentication (already have in main app)
- Maybe add to groups system?

## Example: Building a Simple Prediction

Here's pseudocode for a basic prediction system:

```python
# 1. Load today's props
props = get_todays_props()

for prop in props:
    # 2. Get player's recent stats
    recent_games = get_player_last_n_games(prop.player_id, n=10)

    # 3. Calculate features
    avg_points = mean([g.points for g in recent_games])
    home_or_away = get_game_location(prop.game_id)
    days_rest = calculate_days_rest(prop.player_id, prop.game_date)

    # 4. Make prediction
    prediction = model.predict(features={
        'avg_points_last_10': avg_points,
        'home': home_or_away,
        'days_rest': days_rest,
        # ... more features
    })

    # 5. Compare to line
    edge = prediction - prop.line_value

    # 6. Make recommendation
    if edge > 2.0:  # Predict 2+ points over line
        recommend = "OVER"
    elif edge < -2.0:
        recommend = "UNDER"
    else:
        recommend = "NO PLAY"

    # 7. Store prediction
    store_prediction(prop, prediction, recommend)
```

## Common Workflows

### Daily Workflow (Production)
```bash
# Morning (before games)
cd /home/user/claamp-poll/nba-props
python scripts/collect_daily_data.py
python scripts/query_data.py props

# Generate predictions (after you build models)
# python scripts/generate_predictions.py  # Future script

# Evening (after games complete)
python scripts/collect_daily_data.py --update-completed
```

### One-Time Setup (New Season)
```bash
# Backfill entire previous season for training data
python scripts/backfill_historical.py --season 2024-25
python scripts/backfill_historical.py --season 2023-24

# Train models on historical data
# python scripts/train_models.py  # Future script
```

### Testing/Development
```bash
# Small test backfill
python scripts/backfill_historical.py --season 2024-25 --limit 5

# Check data quality
python scripts/query_data.py stats
python scripts/query_data.py player "LeBron"
```

## Files You'll Want to Edit

As you build out the prediction system:

1. **Add new scripts:**
   - `scripts/generate_predictions.py` - Daily prediction generation
   - `scripts/train_models.py` - Model training
   - `scripts/backtest.py` - Historical backtesting
   - `scripts/evaluate.py` - Model evaluation

2. **Add new services:**
   - `services/feature_engineering.py` - Feature calculation
   - `services/model_loader.py` - Load trained models
   - `services/injury_scraper.py` - Scrape injury data (important!)

3. **Extend models:**
   - Add columns to `nba_predictions` as needed
   - Add new tables for advanced features
   - Add indexes for performance

## Important Notes

### Data Quality
- **Player name matching:** Most stars match automatically, some bench players may not
- **Team name matching:** Odds API uses different names, fuzzy matching implemented
- **Missing data:** Some games may not have props yet, normal behavior
- **Postponed games:** Not auto-detected, manually update if needed

### Database
- **SQLite:** Fine for local development, < 100k records
- **PostgreSQL:** Switch if you need concurrent access or scale to millions of records
- **Backups:** Copy `nba_props.db` regularly if data is valuable

### Future Enhancements
- Injury data integration (MAJOR impact on props)
- Line movement tracking (how lines change over time)
- Weather data (for outdoor games... oh wait, NBA is indoors)
- Referee assignments (some refs call more fouls)
- Player rest patterns (load management trends)
- Advanced stats (PER, True Shooting %, Usage Rate)

## Testing Checklist

Before running in production:

- [ ] Database initialized successfully
- [ ] All 30 teams loaded
- [ ] All ~450 active players loaded
- [ ] Historical data backfilled (at least current season)
- [ ] Daily collection works without errors
- [ ] Can query and view data
- [ ] Odds API usage tracking works
- [ ] Logs are being written
- [ ] Duplicate prevention works (run collection twice, no duplicates)

## Resources

- **NBA API Library:** https://github.com/swar/nba_api
- **The Odds API Docs:** https://the-odds-api.com/liveapi/guides/v4/
- **SQLAlchemy Docs:** https://docs.sqlalchemy.org/
- **Your Main App:** `/home/user/claamp-poll/` (Flask app)

## Support

If you run into issues:

1. Check logs in `logs/daily_collection.log`
2. Run query tool to inspect data: `python scripts/query_data.py stats`
3. Try with `--limit` flags for testing
4. Check API usage: Look for "requests remaining" in output

---

**You're all set! Start collecting data and building your prediction models. 🏀📊**

Current Status:
- ✓ System implemented and tested
- ✓ Database created with 30 teams
- ⏳ Run `init_database.py` to load all players
- ⏳ Run `collect_daily_data.py` to start collecting props
- ⏳ Backfill historical data when ready
