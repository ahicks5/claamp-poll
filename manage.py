# manage.py
from db import Base, engine
from models import *  # ensures models are imported/registered

if __name__ == "__main__":
    Base.metadata.create_all(engine)
    print("✅ Tables created (or already exist).")

