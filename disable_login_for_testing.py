"""
Temporary script to disable login requirement for testing
Run this to modify app.py to auto-login as admin
"""

print("🔧 Adding auto-login for testing...")

# Read app.py
with open('app.py', 'r') as f:
    content = f.read()

# Add auto-login before_request handler
auto_login_code = '''
# ============================================================
# TESTING: AUTO-LOGIN (REMOVE IN PRODUCTION!)
# ============================================================
from flask_login import login_user

@app.before_request
def auto_login_for_testing():
    """Automatically login as admin for testing (REMOVE THIS!)"""
    if not current_user.is_authenticated:
        db = SessionLocal()
        user = db.query(User).filter(User.username == "ahicks5").first()
        if user:
            login_user(user)
        db.close()

'''

# Insert after login_manager setup
insert_after = "login_manager.init_app(app)"
if insert_after in content and "auto_login_for_testing" not in content:
    content = content.replace(insert_after, insert_after + "\n" + auto_login_code)
    
    with open('app.py', 'w') as f:
        f.write(content)
    
    print("✅ Auto-login enabled!")
    print("   You can now visit http://localhost:5057 without logging in")
    print("   ⚠️  REMOVE THIS BEFORE DEPLOYING!")
else:
    print("⚠️  Auto-login already enabled or couldn't find insertion point")
