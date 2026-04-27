import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import app.db as db

conn = db.get_connection()
area = conn.execute("SELECT id FROM areas WHERE LOWER(name) = 'surrey'").fetchone()
if not area:
    print("Surrey not found in areas table — adding it.")
    conn.execute("INSERT INTO areas (name) VALUES ('Surrey')")
    conn.commit()
    area = conn.execute("SELECT id FROM areas WHERE LOWER(name) = 'surrey'").fetchone()

cur = conn.execute("""
    INSERT OR IGNORE INTO supplier_areas (supplier_id, area_id)
    SELECT s.id, ?
    FROM suppliers s
    LEFT JOIN supplier_areas sa ON sa.supplier_id = s.id AND sa.area_id = ?
    WHERE sa.supplier_id IS NULL AND s.id > 1054
""", (area[0], area[0]))
conn.commit()
print(f"Linked {cur.rowcount} suppliers to Surrey.")
conn.close()
