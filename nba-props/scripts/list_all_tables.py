#!/usr/bin/env python3
"""List ALL tables in the database."""
import os
from sqlalchemy import create_engine, inspect, text

database_url = os.getenv('DATABASE_URL', os.getenv('NBA_DATABASE_URL'))

if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

engine = create_engine(database_url)

print("="*60)
print("ALL TABLES IN DATABASE")
print("="*60)

with engine.connect() as conn:
    # Get all tables from information_schema
    result = conn.execute(text("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        ORDER BY table_name
    """))

    tables = [row[0] for row in result]

    print(f"\nTotal tables: {len(tables)}\n")

    for table in tables:
        # Count rows in each table
        try:
            count_result = conn.execute(text(f'SELECT COUNT(*) FROM "{table}"'))
            count = count_result.scalar()
            print(f"  {table:40s} {count:>10,} rows")
        except Exception as e:
            print(f"  {table:40s} (error counting)")

print("")
