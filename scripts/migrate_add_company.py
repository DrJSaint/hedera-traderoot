"""
Migration: Add company column to designers table.
Run from scripts/ folder: python migrate_add_company.py
"""

import sqlite3

DB_PATH = "../database/traderoot.db"

def migrate():
    conn = sqlite3.connect(DB_PATH)
    
    # Check if column already exists
    cols = [row[1] for row in conn.execute("PRAGMA table_info(designers)").fetchall()]
    if "company" in cols:
        print("Column already exists — skipping.")
        conn.close()
        return

    conn.execute("ALTER TABLE designers ADD COLUMN company TEXT")
    conn.commit()
    conn.close()
    print("Added 'company' column to designers table.")

if __name__ == "__main__":
    migrate()
