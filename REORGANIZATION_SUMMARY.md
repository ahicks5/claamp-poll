# TakeFreePoints.com - Reorganization Summary

## What We Did

### 1. ✅ Database Restored
- **Main Database** (`claamp_poll.db`):
  - Users table with admin account (`ahicks5`)
  - New models: Strategy, BetJournal, DailyPerformance, BankrollHistory
  - Initial strategy created: NBA Props with $100 bankroll, 25% Kelly sizing

- **NBA Props Database** (`nba_props.db`):
  - Verified intact with all ML models and predictions

### 2. ✅ Old Features Archived
Moved to `/archived/`:
- `/poll/` - NCAA Top 25 polls
- `/spreads/` - NCAA spread picks
- `/groups/` - Groups system
- `/admin/` - Admin dashboard
- All related templates, scripts, and utilities

### 3. ✅ New "Hedge Fund" Architecture

**Core Models** (`models.py`):
- `User` - Authentication
- `Strategy` - Betting strategy configuration (edge thresholds, Kelly sizing, bankroll management)
- `BetJournal` - Complete bet tracking (predictions → actual bets → results)
- `DailyPerformance` - Aggregated daily metrics (win rate, ROI, P&L)
- `BankrollHistory` - Bankroll snapshots over time

**Utilities** (`utils/betting.py`):
- Kelly Criterion bet sizing
- American ↔ Decimal odds conversion
- Win probability estimation from edge
- Profit/loss calculations

**Services** (`services/strategy_service.py`):
- Auto-filter predictions by strategy criteria (min edge, prop types)
- Calculate optimal bet sizes using Kelly Criterion
- Auto-generate BetJournal entries from daily NBA predictions
- Track bankroll changes

**Bridge Module** (`nba_props_models.py`):
- Connects main app to NBA props database
- Fetches today's predictions with all relevant data

**Routes** (`dashboard/routes.py`):
- `/dashboard/` - Today's action (bankroll, plays, pending bets)
- `/dashboard/generate-bets` - Auto-create bets from predictions
- `/dashboard/bet-journal` - View all bets with filtering
- `/dashboard/performance` - Analytics and charts
- `/dashboard/strategies` - Manage strategies

**Updated App** (`app.py`):
- Removed old blueprints (polls, spreads, groups, admin)
- Added dashboard blueprint
- Simplified to TakeFreePoints.com branding
- Public homepage → Dashboard if logged in

### 4. ✅ Initial Setup

**Your Admin Account**:
- Username: `ahicks5`
- Email: `arhicks14@yahoo.com`
- Password: `ihateAndrew0!`

**Initial Strategy**:
- Name: NBA Props - Main Strategy
- Sport: NBA (player props - points only for now)
- Min Edge: 1.5 points
- Starting Bankroll: $100.00
- Bet Sizing: Kelly Criterion (25% Kelly for conservative sizing)
- Max Bet: $20.00 (20% of initial bankroll)
- Max Daily Bets: 10

## How to Use

### Daily Workflow

1. **Check Predictions**: NBA props ML model generates daily predictions
   ```bash
   cd nba-props
   python scripts/daily_workflow.py
   ```

2. **Login**: Visit site and login with your admin account

3. **Dashboard**: View:
   - Current bankroll
   - Today's recommended plays (filtered by your strategy)
   - Pending bets
   - Recent performance

4. **Generate Bets**: Click "Auto-Generate Bets" to:
   - Filter predictions by min edge (1.5 points)
   - Calculate optimal bet sizes using Kelly Criterion
   - Create BetJournal entries automatically
   - Track stake amounts and potential profits

5. **Track Results**: After games complete:
   - Update bet statuses (won/lost/push)
   - Calculate actual P&L
   - Update bankroll
   - View performance analytics

### Manual Bet Entry

Instead of auto-generating, you can manually:
1. Review recommended plays on dashboard
2. Place bets with your sportsbook
3. Record results in bet journal

## Next Steps (When You're Ready)

### Immediate
- [ ] Run `python app.py` to test the application
- [ ] Login and explore the dashboard
- [ ] Generate test bets from predictions
- [ ] Add more prop types (rebounds, assists) to strategy

### Short-term
- [ ] Create better templates with charts (Chart.js for performance viz)
- [ ] Add result settlement workflow (update bet statuses after games)
- [ ] Build public results page (showcase performance without login)
- [ ] Add strategy management UI (create/edit strategies)

### Medium-term
- [ ] Add NFL props when season starts
- [ ] Implement line movement tracking
- [ ] Add injury data integration
- [ ] Expected Value (EV) calculations with odds
- [ ] Historical backtest of strategy performance

### Long-term
- [ ] Multi-sport support (NFL, MLB, NHL)
- [ ] Multiple concurrent strategies
- [ ] Strategy sharing/copying
- [ ] Mobile app

## File Structure

```
/home/user/claamp-poll/
├── app.py                      # Main Flask app (updated)
├── db.py                       # Database connection
├── models.py                   # New hedge fund models
├── nba_props_models.py         # Bridge to NBA props DB
├── init_database.py            # Database initialization script
│
├── auth/                       # Authentication (unchanged)
├── dashboard/                  # NEW - Main betting dashboard
│   └── routes.py
│
├── nba_props/                  # Flask integration (minimal)
├── nba-props/                  # ML system (unchanged)
│   ├── database/
│   ├── services/
│   ├── scripts/
│   └── models/
│
├── services/                   # NEW - Business logic
│   └── strategy_service.py
│
├── utils/                      # NEW - Utilities
│   └── betting.py             # Kelly Criterion, odds, etc.
│
├── templates/
│   ├── base.html              # Updated base template
│   ├── home.html              # New landing page
│   └── dashboard/             # NEW - Dashboard templates
│       └── index.html
│
└── archived/                   # OLD - Moved here
    ├── poll/
    ├── spreads/
    ├── groups/
    ├── admin/
    ├── scripts/
    └── templates/
```

## Configuration

**Environment Variables** (`.env`):
```
FLASK_ENV=development
SECRET_KEY=test123
DATABASE_URL=sqlite:///claamp_poll.db
NBA_DATABASE_URL=sqlite:///nba_props.db
ODDS_API_KEY=b44a2c02461d44ca702b17ca391a0b31
```

## Testing

```bash
# Initialize database
python init_database.py

# Test Kelly Criterion
python utils/betting.py

# Test strategy service
python services/strategy_service.py

# Run app
python app.py
# Visit: http://localhost:5057
```

## Deployment

The app is ready for Heroku:
- `Procfile` exists
- PostgreSQL support built-in
- Gunicorn configured

Update database URL for production:
```
DATABASE_URL=postgresql://...
NBA_DATABASE_URL=postgresql://...
```

---

**Status**: ✅ Core reorganization complete. Ready for testing and iteration.

**Next**: Test the app, refine templates, add result tracking workflow.
