"""
Initialise the Hedera TradeRoot database.
Run once on first setup: python database/init_db.py
"""

import os
import sqlite3

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(ROOT_DIR, "database", "traderoot.db")
SCHEMA_PATH = os.path.join(ROOT_DIR, "database", "schema.sql")

AREAS = [
    "London", "Kent", "Surrey", "East Sussex", "West Sussex",
    "Hertfordshire", "Essex", "Berkshire", "Hampshire", "Oxfordshire",
]

CATEGORIES = [
    ("Trees", "Living"),
    ("Shrubs", "Living"),
    ("Perennials", "Living"),
    ("Grasses", "Living"),
    ("Alpine", "Living"),
    ("Hedging", "Living"),
    ("Climbers", "Living"),
    ("Paving", "Non-living"),
    ("Gravel", "Non-living"),
    ("Decking", "Non-living"),
    ("Fencing", "Non-living"),
    ("Trellis", "Non-living"),
    ("Pergola/Arbour", "Non-living"),
]


def init_db():
    if os.path.exists(DB_PATH):
        print(f"Database already exists at {DB_PATH} — skipping init.")
        return DB_PATH

    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    with sqlite3.connect(DB_PATH) as conn:
        with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
            conn.executescript(f.read())

        conn.executemany(
            "INSERT OR IGNORE INTO areas (name) VALUES (?)",
            [(area,) for area in AREAS],
        )
        conn.executemany(
            "INSERT OR IGNORE INTO categories (name, group_name) VALUES (?, ?)",
            CATEGORIES,
        )
        conn.execute(
            "INSERT OR IGNORE INTO designers (name, email) VALUES (?, ?)",
            ("Eleanor", "eleanor@hederagardendesign.co.uk"),
        )
        conn.commit()

    print(f"Database initialised at {DB_PATH}")
    return DB_PATH


if __name__ == "__main__":
    init_db()
