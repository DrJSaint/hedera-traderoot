"""
Update supplier types based on HTA tags stored in notes field.
Run from project root: python scripts/update_types.py
"""

import sqlite3
import os

DB_PATH = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "database", "traderoot.db"))

# Keyword to type mapping — order matters, first match wins
# All comparisons are case-insensitive
MAPPINGS = [
    ("landscaper",       "hard_landscaper"),
    ("landscape",        "hard_landscaper"),
    ("nursery",          "nursery"),
    ("grower",           "nursery"),
    ("furniture",        "furniture"),
    ("lighting",         "lighting"),
    ("tool",             "tools"),
    ("equipment",        "tools"),
    ("retailer",         "other"),
    ("manufacturer",     "other"),
    ("service provider", "other"),
]

def update_types():
    conn = sqlite3.connect(DB_PATH)
    updated = 0

    rows = conn.execute(
        "SELECT id, notes FROM suppliers WHERE notes IS NOT NULL"
    ).fetchall()

    for row in rows:
        supplier_id, notes = row
        new_type = None

        for keyword, mapped_type in MAPPINGS:
            if keyword in (notes or "").lower():
                new_type = mapped_type
                break

        if new_type:
            conn.execute(
                "UPDATE suppliers SET type = ? WHERE id = ?",
                (new_type, supplier_id)
            )
            updated += 1

    conn.commit()
    conn.close()
    print(f"Updated {updated} supplier types.")

    # Show summary
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT type, COUNT(*) as count FROM suppliers GROUP BY type ORDER BY count DESC"
    ).fetchall()
    print("\nType breakdown:")
    for r in rows:
        print(f"  {r[0]}: {r[1]}")
    conn.close()

if __name__ == "__main__":
    update_types()
