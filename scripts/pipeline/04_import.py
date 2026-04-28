"""
Stage 4 — Import approved records into traderoot.db.

Usage:
    python scripts/pipeline/04_import.py             # import all approved
    python scripts/pipeline/04_import.py "Surrey"    # import one county

Produces two outputs:
  database/traderoot.db               — existing data + new records merged in
  database/traderoot_<county>_clean.db — fresh database with only the new records
"""

import json
import os
import shutil
import sqlite3
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import app.db as main_db
from scripts.pipeline.staging_db import init_db, get_connection as staging_conn

DB_PATH    = main_db.DB_PATH
DB_DIR     = os.path.dirname(DB_PATH)
BACKUP_DIR = os.path.join(DB_DIR, "backups")


def backup_db():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest  = os.path.join(BACKUP_DIR, f"traderoot_{stamp}.db")
    shutil.copy2(DB_PATH, dest)
    print(f"Backup saved: {dest}")
    return dest


def write_record(conn, r, county: str | None = None):
    """Insert one approved record into the given sqlite3 connection. Returns new id."""
    notes = r["notes"] or ""
    if r["trade_only"]:
        notes = ("Trade/wholesale. " + notes).strip()

    cur = conn.execute(
        """INSERT INTO suppliers (name, type, website, phone, email, price_band, notes, latitude, longitude, trade_only)
           VALUES (?, ?, ?, ?, NULL, NULL, ?, ?, ?, ?)""",
        (r["name"], r["supplier_type"] or "other", r["website"],
         r["phone"], notes or None, r["lat"], r["lon"], 1 if r["trade_only"] else 0),
    )
    sid = cur.lastrowid

    # Link to county area and mark it as primary
    if county:
        area_row = conn.execute("SELECT id FROM areas WHERE LOWER(name) = LOWER(?)", (county,)).fetchone()
        if area_row:
            conn.execute(
                "INSERT OR IGNORE INTO supplier_areas (supplier_id, area_id) VALUES (?,?)",
                (sid, area_row[0])
            )
            conn.execute(
                "UPDATE suppliers SET primary_area_id = ? WHERE id = ?",
                (area_row[0], sid)
            )

    cats = json.loads(r["categories"] or "[]")
    if cats:
        cat_rows = conn.execute(
            f"SELECT id FROM categories WHERE name IN ({','.join('?'*len(cats))})", cats
        ).fetchall()
        for cat in cat_rows:
            conn.execute(
                "INSERT OR IGNORE INTO supplier_categories (supplier_id, category_id) VALUES (?,?)",
                (sid, cat[0])
            )
    return sid


def build_clean_db(rows, county: str):
    """Create a fresh database containing only the pipeline records."""
    label    = (county or "all").replace(" ", "_").lower()
    clean_path = os.path.join(DB_DIR, f"traderoot_{label}_clean.db")

    # Start from a copy of the current schema (areas, categories etc.) but no suppliers
    shutil.copy2(DB_PATH, clean_path)
    conn = sqlite3.connect(clean_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("DELETE FROM reviews")
    conn.execute("DELETE FROM supplier_categories")
    conn.execute("DELETE FROM supplier_areas")
    conn.execute("DELETE FROM suppliers")
    conn.commit()

    for r in rows:
        write_record(conn, r, county)
    conn.commit()
    conn.close()
    print(f"Clean DB:  {clean_path}  ({len(rows)} records)")
    return clean_path


def build_refreshed_db(rows, county: str):
    """Full DB with old county suppliers replaced by new pipeline records."""
    label          = (county or "all").replace(" ", "_").lower()
    refreshed_path = os.path.join(DB_DIR, f"traderoot_{label}_refreshed.db")

    shutil.copy2(DB_PATH, refreshed_path)
    conn = sqlite3.connect(refreshed_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")

    # Find and delete suppliers previously associated with this county
    old_ids = [r[0] for r in conn.execute("""
        SELECT DISTINCT s.id FROM suppliers s
        JOIN supplier_areas sa ON sa.supplier_id = s.id
        JOIN areas a ON a.id = sa.area_id
        WHERE LOWER(a.name) = LOWER(?)
    """, (county,)).fetchall()]

    if old_ids:
        placeholders = ','.join('?' * len(old_ids))
        conn.execute(f"DELETE FROM reviews             WHERE supplier_id IN ({placeholders})", old_ids)
        conn.execute(f"DELETE FROM supplier_categories WHERE supplier_id IN ({placeholders})", old_ids)
        conn.execute(f"DELETE FROM supplier_areas      WHERE supplier_id IN ({placeholders})", old_ids)
        conn.execute(f"DELETE FROM suppliers           WHERE id          IN ({placeholders})", old_ids)
        conn.commit()
        print(f"Removed {len(old_ids)} old {county} suppliers from refreshed DB")

    for r in rows:
        write_record(conn, r, county)
    conn.commit()
    conn.close()
    print(f"Refreshed DB: {refreshed_path}  ({len(rows)} new + existing other counties)")
    return refreshed_path


def import_approved(county: str | None = None):
    init_db()
    conn = staging_conn()

    query = """
        SELECT r.place_id, r.name, r.address, r.phone, r.website, r.lat, r.lon,
               e.supplier_type, e.trade_only, e.categories, e.notes
        FROM enriched e
        JOIN raw_places r ON r.place_id = e.place_id
        WHERE e.approved = 1
    """
    params = []
    if county:
        query += " AND r.search_county = ?"
        params.append(county)

    rows = conn.execute(query, params).fetchall()
    conn.close()

    if not rows:
        print("No approved records to import.")
        return

    # ── Clean DB (pipeline data only) ────────────────────────────────────────
    build_clean_db(rows, county or "all")

    # ── Live DB: clean replace (when county given) or additive merge (no county) (old county records out, new ones in) ──────────
    backup_db()
    if county:
        mconn = sqlite3.connect(DB_PATH)
        mconn.row_factory = sqlite3.Row
        mconn.execute("PRAGMA foreign_keys = ON")

        old_ids = [r[0] for r in mconn.execute("""
            SELECT DISTINCT s.id FROM suppliers s
            JOIN supplier_areas sa ON sa.supplier_id = s.id
            JOIN areas a ON a.id = sa.area_id
            WHERE LOWER(a.name) = LOWER(?)
        """, (county,)).fetchall()]

        if old_ids:
            placeholders = ','.join('?' * len(old_ids))
            mconn.execute(f"DELETE FROM reviews             WHERE supplier_id IN ({placeholders})", old_ids)
            mconn.execute(f"DELETE FROM supplier_categories WHERE supplier_id IN ({placeholders})", old_ids)
            mconn.execute(f"DELETE FROM supplier_areas      WHERE supplier_id IN ({placeholders})", old_ids)
            mconn.execute(f"DELETE FROM suppliers           WHERE id          IN ({placeholders})", old_ids)
            mconn.commit()
            print(f"Removed {len(old_ids)} old {county} suppliers")

        for r in rows:
            write_record(mconn, r, county)
            print(f"  IMPORT: {r['name']} ({r['supplier_type']})")
        mconn.commit()
        mconn.close()
        print(f"\nDone. {len(rows)} imported (clean replace) into {DB_PATH}")
    else:
        # No county filter — additive merge across all
        existing = {s["name"].lower() for s in main_db.get_suppliers()}
        imported = skipped = 0
        mconn = main_db.get_connection()
        for r in rows:
            if r["name"].lower() in existing:
                skipped += 1
                continue
            write_record(mconn, r, county)
            existing.add(r["name"].lower())
            imported += 1
            print(f"  IMPORT: {r['name']} ({r['supplier_type']})")
        mconn.commit()
        mconn.close()
        print(f"\nDone. {imported} imported, {skipped} skipped (already exist).")


if __name__ == "__main__":
    county = sys.argv[1] if len(sys.argv) > 1 else None
    import_approved(county)
