"""
HTA All-Members Import Script
Reads hta_members_all.csv, maps member_type to supplier type,
skips names already in the database, and bulk inserts the rest.
Run from the project root: python scripts/import_hta_all.py
"""

import sqlite3
import csv
import os

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.normpath(os.path.join(_SCRIPTS_DIR, "..", "database", "traderoot.db"))
CSV_PATH = os.path.normpath(os.path.join(_SCRIPTS_DIR, "..", "data", "hta_members_all.csv"))

TYPE_MAP = {
    "landscaper":       "hard_landscaper",
    "grower":           "nursery",
    "retailer":         "other",
    "online retailer":  "other",
    "service provider": "other",
}


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_or_create_area(conn, area_name):
    row = conn.execute("SELECT id FROM areas WHERE name = ?", (area_name,)).fetchone()
    if row:
        return row["id"]
    cur = conn.execute("INSERT INTO areas (name) VALUES (?)", (area_name,))
    return cur.lastrowid


def import_members():
    if not os.path.exists(CSV_PATH):
        print(f"CSV not found at {CSV_PATH}")
        return

    with get_connection() as conn:
        existing = {
            row[0].lower()
            for row in conn.execute("SELECT name FROM suppliers").fetchall()
        }

        imported = 0
        skipped = 0

        with open(CSV_PATH, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))

        for row in rows:
            name = row["name"].strip()
            if name.lower() in existing:
                skipped += 1
                continue

            raw_type = row.get("member_type", "").strip().lower()
            supplier_type = TYPE_MAP.get(raw_type, "other")

            county = row.get("county", "").strip()
            if "london" in county.lower():
                county = "London"

            notes = f"HTA tags: {row['tags']} | Territory: {row['territory']}"

            cur = conn.execute(
                """INSERT INTO suppliers (name, type, website, phone, email, notes, latitude, longitude)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    name,
                    supplier_type,
                    row.get("website") or None,
                    row.get("phone") or None,
                    row.get("email") or None,
                    notes,
                    row.get("lat") or None,
                    row.get("lng") or None,
                ),
            )

            if county:
                area_id = get_or_create_area(conn, county)
                conn.execute(
                    "INSERT OR IGNORE INTO supplier_areas (supplier_id, area_id) VALUES (?, ?)",
                    (cur.lastrowid, area_id),
                )

            imported += 1

        conn.commit()

    print(f"Done — {imported} imported, {skipped} skipped (already in DB).")


if __name__ == "__main__":
    import_members()
