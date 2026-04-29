"""
Reset enriched records for a county so they can be re-enriched.

Usage:
    python scripts/pipeline/reset_county.py "East Sussex"
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from scripts.pipeline.staging_db import get_connection


def reset(county: str):
    conn = get_connection()
    cur = conn.execute("""
        DELETE FROM enriched
        WHERE place_id IN (
            SELECT place_id FROM raw_places WHERE search_county = ?
        )
    """, (county,))
    conn.commit()
    conn.close()
    print(f"Cleared {cur.rowcount} enriched records for {county}.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("Usage: python reset_county.py <county>")
    reset(sys.argv[1])
