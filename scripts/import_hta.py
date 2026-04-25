"""
HTA Member Import Script
Reads hta_members.csv and bulk inserts ALL members into traderoot.db.
County and territory are stored so the app can filter by region.
Run from the project root: python import_hta.py
"""

import sqlite3
import csv
import os

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.normpath(os.path.join(_SCRIPTS_DIR, "..", "database", "traderoot.db"))
CSV_PATH = os.path.normpath(os.path.join(_SCRIPTS_DIR, "..", "data", "hta_members.csv"))

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def get_or_create_area(conn, area_name):
    """Get area id, creating it if it doesn't exist."""
    row = conn.execute(
        "SELECT id FROM areas WHERE name = ?", (area_name,)
    ).fetchone()
    if row:
        return row["id"]
    cur = conn.execute(
        "INSERT INTO areas (name) VALUES (?)", (area_name,)
    )
    return cur.lastrowid

def import_members():
    if not os.path.exists(CSV_PATH):
        print(f"CSV not found at {CSV_PATH} — run scrape_hta.py first.")
        return

    with get_connection() as conn:
        imported = 0

        with open(CSV_PATH, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                county = row["county"].strip()
                if "london" in county.lower():
                    county = "London"

                # Insert supplier — store territory in notes for now
                notes = f"HTA tags: {row['tags']} | Territory: {row['territory']}"

                cur = conn.execute(
                    """INSERT INTO suppliers 
                       (name, type, website, phone, email, notes, latitude, longitude)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        row["name"],
                        "other",
                        row["website"],
                        row["phone"],
                        row["email"],
                        notes,
                        row["lat"] or None,
                        row["lng"] or None,
                    )
                )
                supplier_id = cur.lastrowid

                # Link to county as area
                if county:
                    area_id = get_or_create_area(conn, county)
                    conn.execute(
                        "INSERT OR IGNORE INTO supplier_areas (supplier_id, area_id) VALUES (?, ?)",
                        (supplier_id, area_id)
                    )

                imported += 1
                print(f"  Imported: {row['name']} — {county}")

        conn.commit()
        print(f"\nDone — {imported} suppliers imported.")

if __name__ == "__main__":
    import_members()
