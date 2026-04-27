import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from scripts.pipeline.staging_db import get_connection

conn = get_connection()
cur = conn.execute("DELETE FROM enriched WHERE notes LIKE 'Error:%' OR relevant IS NULL")
conn.commit()
print(f"Cleared {cur.rowcount} failed records — ready to re-enrich.")
conn.close()
