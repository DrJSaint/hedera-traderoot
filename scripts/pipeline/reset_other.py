"""Reset 'other' enriched records so they get re-classified with the updated prompt."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from scripts.pipeline.staging_db import get_connection

conn = get_connection()
cur = conn.execute("DELETE FROM enriched WHERE supplier_type = 'other'")
conn.commit()
print(f"Reset {cur.rowcount} 'other' records — ready to re-enrich.")
conn.close()
