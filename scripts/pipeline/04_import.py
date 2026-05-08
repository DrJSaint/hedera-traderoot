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
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy import text

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import app.db as main_db
from app.database_config import DEFAULT_SQLITE_PATH, get_sqlite_db_path
from app.live_db import get_engine
from scripts.pipeline.staging_db import init_db, get_connection as staging_conn

DB_PATH    = get_sqlite_db_path()
DB_DIR     = DEFAULT_SQLITE_PATH.parent
BACKUP_DIR = os.path.join(DB_DIR, "backups")
ENGINE     = get_engine()


def _insert_ignore_sql(table: str, columns: list[str], conflict_columns: list[str], dialect_name: str) -> str:
    column_list = ", ".join(columns)
    value_list = ", ".join(f":{column}" for column in columns)
    if dialect_name == "postgresql":
        conflicts = ", ".join(conflict_columns)
        return (
            f"INSERT INTO {table} ({column_list}) VALUES ({value_list}) "
            f"ON CONFLICT ({conflicts}) DO NOTHING"
        )
    return f"INSERT OR IGNORE INTO {table} ({column_list}) VALUES ({value_list})"


def _insert_returning_id(conn, query: str, params: dict) -> int:
    if conn.dialect.name == "postgresql":
        return conn.execute(text(f"{query} RETURNING id"), params).scalar_one()
    result = conn.execute(text(query), params)
    return int(result.lastrowid)


def _in_clause(prefix: str, values: list) -> tuple[str, dict]:
    params = {f"{prefix}_{index}": value for index, value in enumerate(values)}
    placeholders = ", ".join(f":{key}" for key in params)
    return placeholders, params


def _copy_reference_data(source_conn, target_conn):
    for table in ("areas", "categories", "designers"):
        rows = source_conn.execute(text(f"SELECT * FROM {table}"))
        mappings = [dict(row) for row in rows.mappings().all()]
        if not mappings:
            continue
        columns = list(mappings[0].keys())
        insert_sql = text(
            f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({', '.join(f':{column}' for column in columns)})"
        )
        target_conn.execute(insert_sql, mappings)


def _build_clean_sqlite_db(clean_path: Path):
    if clean_path.exists():
        clean_path.unlink()

    alembic_cfg = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", f"sqlite:///{clean_path.as_posix()}")
    command.upgrade(alembic_cfg, "head")
    return create_engine(
        f"sqlite:///{clean_path.as_posix()}",
        future=True,
        connect_args={"check_same_thread": False},
    )


def _find_supplier_ids_for_county(conn, county: str) -> list[int]:
    rows = conn.execute(
        text(
            """SELECT DISTINCT s.id FROM suppliers s
               JOIN supplier_areas sa ON sa.supplier_id = s.id
               JOIN areas a ON a.id = sa.area_id
               WHERE LOWER(a.name) = LOWER(:county)"""
        ),
        {"county": county},
    )
    return [row[0] for row in rows.fetchall()]


def _delete_supplier_ids(conn, supplier_ids: list[int]):
    if not supplier_ids:
        return

    placeholders, params = _in_clause("supplier_id", supplier_ids)
    conn.execute(text(f"DELETE FROM reviews WHERE supplier_id IN ({placeholders})"), params)
    conn.execute(text(f"DELETE FROM supplier_categories WHERE supplier_id IN ({placeholders})"), params)
    conn.execute(text(f"DELETE FROM supplier_areas WHERE supplier_id IN ({placeholders})"), params)
    conn.execute(text(f"DELETE FROM suppliers WHERE id IN ({placeholders})"), params)


def _reference_lookup(conn, county: str | None) -> tuple[dict[str, int], int | None]:
    category_rows = conn.execute(text("SELECT id, name FROM categories"))
    category_map = {row[1]: row[0] for row in category_rows.fetchall()}
    area_id = None
    if county:
        area_id = conn.execute(
            text("SELECT id FROM areas WHERE LOWER(name) = LOWER(:county)"),
            {"county": county},
        ).scalar()
    return category_map, area_id


def backup_db():
    if not DB_PATH:
        print("Backup skipped: live database is not a local SQLite file.")
        return None

    os.makedirs(BACKUP_DIR, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest  = os.path.join(BACKUP_DIR, f"traderoot_{stamp}.db")
    shutil.copy2(DB_PATH, dest)
    print(f"Backup saved: {dest}")
    return dest


def write_record(conn, r, county: str | None = None, *, category_map: dict[str, int], area_id: int | None = None):
    """Insert one approved record into the given connection. Returns new id."""
    notes = r["notes"] or ""
    if r["trade_only"]:
        notes = ("Trade/wholesale. " + notes).strip()

    sid = _insert_returning_id(
        conn,
        """INSERT INTO suppliers (name, type, website, phone, email, price_band, notes, address, latitude, longitude, trade)
            VALUES (:name, :supplier_type, :website, :phone, NULL, NULL, :notes, :address, :lat, :lon, :trade)""",
        {
            "name": r["name"],
            "supplier_type": r["supplier_type"] or "other",
            "website": r["website"],
            "phone": r["phone"],
            "notes": notes or None,
            "address": r["address"],
            "lat": r["lat"],
            "lon": r["lon"],
            "trade": 1 if r["trade_only"] else 0,
        },
    )

    # Link to county area and mark it as primary
    if county and area_id:
        conn.execute(
            text(
                _insert_ignore_sql(
                    "supplier_areas",
                    ["supplier_id", "area_id"],
                    ["supplier_id", "area_id"],
                    conn.dialect.name,
                )
            ),
            {"supplier_id": sid, "area_id": area_id},
        )
        conn.execute(
            text("UPDATE suppliers SET primary_area_id = :area_id WHERE id = :supplier_id"),
            {"area_id": area_id, "supplier_id": sid},
        )

    cats = json.loads(r["categories"] or "[]")
    if cats:
        insert_sql = text(
            _insert_ignore_sql(
                "supplier_categories",
                ["supplier_id", "category_id"],
                ["supplier_id", "category_id"],
                conn.dialect.name,
            )
        )
        for cat_name in cats:
            category_id = category_map.get(cat_name)
            if not category_id:
                continue
            conn.execute(
                insert_sql,
                {"supplier_id": sid, "category_id": category_id},
            )
    return sid


def build_clean_db(rows, county: str):
    """Create a fresh database containing only the pipeline records."""
    label    = (county or "all").replace(" ", "_").lower()
    clean_path = Path(DB_DIR) / f"traderoot_{label}_clean.db"

    clean_engine = _build_clean_sqlite_db(clean_path)
    with ENGINE.connect() as source_conn, clean_engine.begin() as conn:
        _copy_reference_data(source_conn, conn)
        category_map, area_id = _reference_lookup(conn, county)
        for r in rows:
            write_record(conn, r, county, category_map=category_map, area_id=area_id)

    print(f"Clean DB:  {clean_path}  ({len(rows)} records)")
    clean_engine.dispose()
    return str(clean_path)


def import_approved(county: str | None = None):
    init_db()
    main_db.ensure_schema()
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
        with ENGINE.begin() as mconn:
            category_map, area_id = _reference_lookup(mconn, county)
            old_ids = _find_supplier_ids_for_county(mconn, county)

            if old_ids:
                _delete_supplier_ids(mconn, old_ids)
                print(f"Removed {len(old_ids)} old {county} suppliers")

            for r in rows:
                write_record(mconn, r, county, category_map=category_map, area_id=area_id)
                print(f"  IMPORT: {r['name']} ({r['supplier_type']})")

        target_label = DB_PATH if DB_PATH else ENGINE.url.render_as_string(hide_password=False)
        print(f"\nDone. {len(rows)} imported (clean replace) into {target_label}")
    else:
        # No county filter — additive merge across all
        existing = {s["name"].lower() for s in main_db.get_suppliers()}
        imported = skipped = 0
        with ENGINE.begin() as mconn:
            category_map, area_id = _reference_lookup(mconn, county)
            for r in rows:
                if r["name"].lower() in existing:
                    skipped += 1
                    continue
                write_record(mconn, r, county, category_map=category_map, area_id=area_id)
                existing.add(r["name"].lower())
                imported += 1
                print(f"  IMPORT: {r['name']} ({r['supplier_type']})")
        print(f"\nDone. {imported} imported, {skipped} skipped (already exist).")


if __name__ == "__main__":
    county = sys.argv[1] if len(sys.argv) > 1 else None
    import_approved(county)
