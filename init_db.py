# init_db.py
from db import engine, Base
import models

print("🔧 Creating tables in claamp_poll.db...")
Base.metadata.create_all(bind=engine)
print("✅ Done.")
