"""
Update supplier types based on HTA tags stored in notes field.
Run from project root: python scripts/update_types.py
"""

import sqlite3

DB_PATH = "../database/traderoot.db"

# Keyword to type mapping — order matters, first match wins
MAPPINGS = [
    ("Landscaper",              "hard_landscaper"),
    ("landscape",               "hard_landscaper"),
    ("Nursery",                 "nursery"),
    ("nursery",                 "nursery"),
    ("Grower",                  "nursery"),
    ("grower",                  "nursery"),
    ("Furniture",               "furniture"),
    ("furniture",               "furniture"),
    ("Lighting",                "lighting"),
    ("lighting",                "lighting"),
    ("Tool",                    "tools"),
    ("tool",                    "tools"),
    ("Equipment",               "tools"),
    ("Retailer",                "other"),
    ("Manufacturer",            "other"),
    ("Service Provider",        "other"),
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
            if keyword in (notes or ""):
                new_type = mapped_type
                break

        if new_type and new_type != "other":
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
