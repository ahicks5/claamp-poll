# scripts/ensure_tables.py
from db import engine, Base
# importing models registers all mapped classes on Base.metadata
import models  # noqa: F401

def main():
    # Create any tables that don't exist yet
    Base.metadata.create_all(bind=engine)
    print("✅ Ensured all tables exist.")

if __name__ == "__main__":
    main()
