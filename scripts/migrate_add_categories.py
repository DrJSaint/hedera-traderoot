"""
Migration: Add categories and supplier_categories tables.
Run from project root: python scripts/migrate_add_categories.py
"""

import sqlite3

DB_PATH = "../database/traderoot.db"

CATEGORIES = [
    # Living
    ("Trees",       "Living"),
    ("Shrubs",      "Living"),
    ("Perennials",  "Living"),
    ("Grasses",     "Living"),
    ("Alpine",      "Living"),
    ("Hedging",     "Living"),
    ("Climbers",    "Living"),
    # Non-living
    ("Paving",          "Non-living"),
    ("Gravel",          "Non-living"),
    ("Decking",         "Non-living"),
    ("Fencing",         "Non-living"),
    ("Trellis",         "Non-living"),
    ("Pergola/Arbour",  "Non-living"),
]

def migrate():
    conn = sqlite3.connect(DB_PATH)

    # Add categories table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            name    TEXT NOT NULL UNIQUE,
            group_name TEXT NOT NULL  -- 'Living' or 'Non-living'
        )
    """)

    # Add supplier_categories join table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS supplier_categories (
            supplier_id INTEGER NOT NULL REFERENCES suppliers(id) ON DELETE CASCADE,
            category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
            PRIMARY KEY (supplier_id, category_id)
        )
    """)

    # Seed categories
    conn.executemany(
        "INSERT OR IGNORE INTO categories (name, group_name) VALUES (?, ?)",
        CATEGORIES
    )

    conn.commit()
    conn.close()

    print("Migration complete. Categories seeded:")
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT group_name, name FROM categories ORDER BY group_name, id"
    ).fetchall()
    current_group = None
    for group, name in rows:
        if group != current_group:
            print(f"\n  {group}:")
            current_group = group
        print(f"    - {name}")
    conn.close()

if __name__ == "__main__":
    migrate()
