#!/usr/bin/env python3
"""Check Heroku Postgres backups via API."""
import os
import subprocess
import sys

print("="*60)
print("CHECKING HEROKU POSTGRES BACKUPS")
print("="*60)

# Try to run heroku pg:backups command
try:
    result = subprocess.run(
        ['heroku', 'pg:backups', '--app', os.getenv('HEROKU_APP_NAME', 'claamp-poll')],
        capture_output=True,
        text=True,
        timeout=30
    )

    print("\n" + result.stdout)
    if result.stderr:
        print("Errors:", result.stderr)

except FileNotFoundError:
    print("\nHeroku CLI not available in this environment.")
    print("\nYou need to run this from your LOCAL terminal (not Heroku console):")
    print("  heroku pg:backups")
    print("")
    print("Or go to Heroku Dashboard:")
    print("  1. Go to your app's Resources tab")
    print("  2. Click on 'Heroku Postgres'")
    print("  3. Go to 'Durability' tab")
    print("  4. Check 'Backups' section")

except Exception as e:
    print(f"\nError: {e}")
    print("\nManual steps to check backups:")
    print("  1. Open Heroku Dashboard in browser")
    print("  2. Go to your app")
    print("  3. Click Resources → Heroku Postgres")
    print("  4. Check Durability → Backups")

print("")
