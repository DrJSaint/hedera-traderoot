"""
Initialise the Hedera TradeRoot database.
Run once on first setup: python database/init_db.py
"""

import sqlite3
import os

DB_PATH = "database/traderoot.db"
SCHEMA_PATH = "database/schema.sql"

def init_db():
    if os.path.exists(DB_PATH):
        print(f"Database already exists at {DB_PATH} — skipping init.")
        return

    with sqlite3.connect(DB_PATH) as conn:
        with open(SCHEMA_PATH, "r") as f:
            conn.executescript(f.read())

        # Seed areas
        areas = [
            "London", "Kent", "Surrey", "East Sussex", "West Sussex",
            "Hertfordshire", "Essex", "Berkshire", "Hampshire", "Oxfordshire"
        ]
        conn.executemany(
            "INSERT OR IGNORE INTO areas (name) VALUES (?)",
            [(a,) for a in areas]
        )

        # Seed one demo designer (Eleanor)
        conn.execute(
            "INSERT OR IGNORE INTO designers (name, email) VALUES (?, ?)",
            ("Eleanor", "eleanor@hederagardendesign.co.uk")
        )

        conn.commit()

    print(f"Database initialised at {DB_PATH}")

if __name__ == "__main__":
    init_db()
