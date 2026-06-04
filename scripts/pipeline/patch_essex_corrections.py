"""
Manual corrections for Essex pipeline review.
Run BEFORE 03_review.py approve "Essex".

Usage:
    python scripts/pipeline/patch_essex_corrections.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from scripts.pipeline.staging_db import get_connection

NOT_TRADE = [
    "Grenville Nurseries",
    "Smith W D & Son",
    "Drake Trees Garden Centre",
    "Langthorns Plantery",
    "Trees and Plants Unlimited",
    "King & Co - The Tree Nursery Ltd",
    "Oak Nursery",
    "Hilltop Nursery Ramsden Heath",
    "Westview Nurseries",
    "The Bungalow nursery",
]

NOT_RELEVANT = [
    "PRIMROSE COTTAGE NURSERIES",
    "Weirwood Nursery",
]

WEBSITE_FIXES = {
    "Oak Nursery":               "https://www.facebook.com/oaknurserychelmsford",
    "Hilltop Nursery Ramsden Heath": "https://www.facebook.com/p/Hilltop-Nursery-Ramsden-Heath-Past-Present-and-Future-100063815972794/",
    "The Bungalow nursery":      "https://sites.google.com/a/bungalownursery.co.uk/home/home",
}

conn = get_connection()

for name in NOT_TRADE:
    cur = conn.execute("""
        UPDATE enriched SET trade_only = 0
        WHERE place_id IN (
            SELECT place_id FROM raw_places
            WHERE name LIKE ? AND search_county = 'Essex'
        )
    """, (f"%{name}%",))
    print(f"  Not trade ({cur.rowcount} row): {name}")

for name in NOT_RELEVANT:
    cur = conn.execute("""
        UPDATE enriched SET relevant = 0, approved = 0
        WHERE place_id IN (
            SELECT place_id FROM raw_places
            WHERE name LIKE ? AND search_county = 'Essex'
        )
    """, (f"%{name}%",))
    print(f"  Not relevant ({cur.rowcount} row): {name}")

for name, url in WEBSITE_FIXES.items():
    cur = conn.execute("""
        UPDATE raw_places SET website = ?
        WHERE name LIKE ? AND search_county = 'Essex'
    """, (url, f"%{name}%"))
    print(f"  Website updated ({cur.rowcount} row): {name}")

conn.commit()
conn.close()
print("\nDone. Now run: python scripts/pipeline/03_review.py approve \"Essex\"")
