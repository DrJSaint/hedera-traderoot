"""
Migration: add composite index on (latitude, longitude) for fast proximity queries.
Run once against the live database: python scripts/migrate_add_coords_index.py
"""
import sqlite3
import os

DB_PATH = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "database", "traderoot.db")
)

with sqlite3.connect(DB_PATH) as conn:
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_suppliers_lat_lon ON suppliers(latitude, longitude)"
    )
    conn.commit()

print("Done — index idx_suppliers_lat_lon created (or already existed).")
