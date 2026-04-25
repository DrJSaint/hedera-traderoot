"""
Randomly assign supplier types for demo purposes.
Weighted towards nursery as that's the most relevant for garden designers.
Run from scripts/ folder: python randomise_types.py
"""

import sqlite3
import os
import random

DB_PATH = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "database", "traderoot.db"))

# Weighted distribution — nursery most common
TYPES = (
    ["nursery"] * 40 +
    ["hard_landscaper"] * 25 +
    ["other"] * 15 +
    ["furniture"] * 10 +
    ["tools"] * 7 +
    ["lighting"] * 3
)

def randomise_types():
    conn = sqlite3.connect(DB_PATH)

    rows = conn.execute("SELECT id FROM suppliers").fetchall()
    for row in rows:
        new_type = random.choice(TYPES)
        conn.execute(
            "UPDATE suppliers SET type = ? WHERE id = ?",
            (new_type, row[0])
        )

    conn.commit()

    # Summary
    rows = conn.execute(
        "SELECT type, COUNT(*) as count FROM suppliers GROUP BY type ORDER BY count DESC"
    ).fetchall()
    print("Type distribution:")
    for r in rows:
        print(f"  {r[0]}: {r[1]}")

    conn.close()

if __name__ == "__main__":
    randomise_types()
