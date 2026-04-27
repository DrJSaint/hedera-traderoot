"""
Fix Surrey area links — removes all Surrey associations then re-links
only the suppliers that came from the Surrey pipeline import.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import app.db as db
from scripts.pipeline.staging_db import get_connection as staging_conn

mconn = db.get_connection()
sconn = staging_conn()

# Get area id for Surrey
area = mconn.execute("SELECT id FROM areas WHERE LOWER(name) = 'surrey'").fetchone()
if not area:
    print("Surrey area not found.")
    sys.exit()
area_id = area[0]

# Remove ALL existing Surrey links
cur = mconn.execute("DELETE FROM supplier_areas WHERE area_id = ?", (area_id,))
print(f"Removed {cur.rowcount} existing Surrey area links.")

# Get names of approved Surrey pipeline records
pipeline_names = [r[0].lower() for r in sconn.execute("""
    SELECT r.name FROM raw_places r
    JOIN enriched e ON e.place_id = r.place_id
    WHERE e.approved = 1 AND r.search_county = 'Surrey'
""").fetchall()]
sconn.close()

print(f"Pipeline has {len(pipeline_names)} approved Surrey records.")

# Find matching suppliers in main db and link to Surrey
linked = 0
for name in pipeline_names:
    row = mconn.execute("SELECT id FROM suppliers WHERE LOWER(name) = ?", (name,)).fetchone()
    if row:
        mconn.execute(
            "INSERT OR IGNORE INTO supplier_areas (supplier_id, area_id) VALUES (?,?)",
            (row[0], area_id)
        )
        linked += 1

mconn.commit()
mconn.close()
print(f"Linked {linked} Surrey pipeline suppliers to Surrey area.")
