# TakeFreePoints.com - Testing Guide

## ✅ What's Working Now

### NBA Props Data Collection
- **Odds API**: ✓ Working (7 games, 8 bookmakers)
- **NBA Games API**: ✓ Working
- **Database**: ✓ Initialized (30 teams, 530 players)

## 🧪 Testing Workflow

### Step 1: Test NBA Props Data Collection

```bash
cd /home/user/claamp-poll/nba-props

# Test data collection
python test_data_pipeline.py

# Run full daily workflow (collects games + odds + generates predictions)
python scripts/daily_workflow.py
```

**What this does:**
1. Fetches today's NBA games
2. Gets player prop odds from sportsbooks
3. Generates predictions using ML model
4. Saves to database

**Expected output:**
- Games collected: ~7-15 (depends on day)
- Props collected: ~500-1000 player props
- Predictions generated: ~100-300 (filtered by confidence)

### Step 2: Check What's in the Database

```bash
cd /home/user/claamp-poll/nba-props
python -c "
from database.db import SessionLocal
from database.models import Game, PropLine, Prediction
from datetime import date

db = SessionLocal()
today = date.today()

games = db.query(Game).filter(Game.game_date == today).count()
props = db.query(PropLine).filter(PropLine.is_latest == True).count()
preds = db.query(Prediction).join(Game).filter(Game.game_date == today).count()

print(f'📊 Today ({today}):')
print(f'  Games: {games}')
print(f'  Prop Lines: {props}')
print(f'  Predictions: {preds}')

db.close()
"
```

### Step 3: Test the Web App (Without Login)

I can add a temporary bypass for login so you can test the dashboard.

**Option A: Disable login requirement**
```python
# In app.py, comment out @login_required decorators
```

**Option B: Auto-login as admin**
```python
# Add this to app.py for testing:
@app.before_request
def auto_login():
    if not current_user.is_authenticated:
        from models import User
        from db import SessionLocal
        db = SessionLocal()
        user = db.query(User).filter(User.username == "ahicks5").first()
        if user:
            login_user(user)
        db.close()
```

**Option C: Just login normally** (easiest!)
- Username: `ahicks5`
- Password: `ihateAndrew0!`

### Step 4: Test Dashboard

```bash
cd /home/user/claamp-poll
python app.py

# Visit: http://localhost:5057
```

---

## 🎨 CSS Migration (Do This After Testing NBA Props!)

### Your Old CSS Style
- **Dark theme**: `#0b0d10` background
- **Brand color**: `#6ee7ff` (teal/cyan)
- **Accent**: `#7cffb7` (mint green)
- **Clean, minimal design**

### Quick Fix: Update base.html

Replace the current inline styles with a link to your existing CSS:

```html
<!-- In templates/base.html, replace the <style> block with: -->
<link rel="stylesheet" href="{{ url_for('static', filename='styles/tokens.css') }}">
<link rel="stylesheet" href="{{ url_for('static', filename='styles/base.css') }}">
<link rel="stylesheet" href="{{ url_for('static', filename='styles/cards.css') }}">
<link rel="stylesheet" href="{{ url_for('static', filename='styles/buttons.css') }}">
<link rel="stylesheet" href="{{ url_for('static', filename='styles/nav.css') }}">
<link rel="stylesheet" href="{{ url_for('static', filename='styles/tables.css') }}">
```

This will bring back your old dark theme and styling!

---

## 📁 File Organization

### NBA Props System (Separate Module)
```
/nba-props/
├── database/           # Models & DB connection
├── services/          # API clients (NBA, Odds)
├── scripts/           # Daily workflows
│   ├── daily_workflow.py    # ← Main script to run daily
│   ├── train_model.py       # Train ML model
│   └── track_results.py     # Update bet results
└── models/            # Trained ML models (.pkl files)
```

### Main Web App
```
/home/user/claamp-poll/
├── app.py             # Flask app
├── models.py          # User, Strategy, BetJournal
├── dashboard/         # Dashboard routes
├── services/          # Strategy service
├── utils/             # Kelly Criterion
└── nba_props_models.py  # Bridge to NBA props DB
```

### Testing Files (I Created)
```
/nba-props/
└── test_data_pipeline.py   # Test games + odds

/home/user/claamp-poll/
└── TESTING_GUIDE.md        # This file!
```

---

## 🚀 Recommended Order

1. **Test NBA Props** (30 min)
   - Run `daily_workflow.py`
   - Verify data is collecting properly
   - Check predictions are generated

2. **Fix CSS** (15 min)
   - Update base.html to use old CSS files
   - Test that dark theme is back

3. **Test Web App** (15 min)
   - Login and view dashboard
   - Click "Auto-Generate Bets"
   - Verify bets are created with Kelly sizing

4. **Iterate**
   - Refine strategy settings (edge threshold, etc.)
   - Improve dashboard UI
   - Add charts/visualizations

---

## 🐛 Common Issues

### "No predictions generated"
- Model might not be trained yet
- Run: `python scripts/train_model.py`

### "No props available"
- Check if there are games today
- Odds API might not have props yet (usually available ~24hrs before game)

### "Database empty"
- Run `python scripts/init_database.py` in nba-props/
- Then run `python scripts/daily_workflow.py`

### "Login not working"
- Run `python init_database.py` in main directory
- This recreates admin user

---

## ✅ Success Checklist

- [ ] NBA Props database initialized (30 teams, 530 players)
- [ ] Daily workflow runs successfully (games + odds + predictions)
- [ ] Can see predictions in database
- [ ] Web app starts without errors
- [ ] Can login (or bypass for testing)
- [ ] Dashboard shows today's plays
- [ ] Auto-generate bets works
- [ ] Bets appear in bet journal
- [ ] Old CSS is back (dark theme)

---

Let me know which phase you want to tackle first!
