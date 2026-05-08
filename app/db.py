"""
Database access layer for Hedera TradeRoot.
All SQL lives here. Returns plain dicts/lists — no pandas dependency.
"""

import math
import os
import sqlite3

from sqlalchemy import text

from app.database_config import get_sqlite_db_path, uses_sqlite
from app.live_db import get_engine

DB_PATH = get_sqlite_db_path()
ENGINE = get_engine()

_SCHEMA_READY = False


def ensure_schema():
    global _SCHEMA_READY
    if _SCHEMA_READY:
        return

    if not uses_sqlite() or not DB_PATH:
        _SCHEMA_READY = True
        return

    with sqlite3.connect(DB_PATH) as conn:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(suppliers)").fetchall()}
        if "address" not in cols:
            conn.execute("ALTER TABLE suppliers ADD COLUMN address TEXT")
            conn.commit()

    _SCHEMA_READY = True


def get_connection():
    if not DB_PATH:
        raise RuntimeError("app.db currently supports only SQLite connections. Configure SQLite locally or migrate this caller to the shared Postgres layer.")

    ensure_schema()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _connect():
    ensure_schema()
    return ENGINE.connect()


def _begin():
    ensure_schema()
    return ENGINE.begin()


def _rows_to_dicts(result) -> list[dict]:
    return [dict(row) for row in result.mappings().all()]


def _fetch_all(query: str, params: dict | None = None) -> list[dict]:
    with _connect() as conn:
        return _rows_to_dicts(conn.execute(text(query), params or {}))


def _fetch_one(query: str, params: dict | None = None) -> dict | None:
    with _connect() as conn:
        row = conn.execute(text(query), params or {}).mappings().first()
    return dict(row) if row else None


def _insert_returning_id(conn, query: str, params: dict) -> int:
    if conn.dialect.name == "postgresql":
        return conn.execute(text(f"{query} RETURNING id"), params).scalar_one()
    result = conn.execute(text(query), params)
    return int(result.lastrowid)


def _insert_ignore_sql(table: str, columns: list[str], conflict_columns: list[str]) -> str:
    column_list = ", ".join(columns)
    value_list = ", ".join(f":{column}" for column in columns)
    if ENGINE.dialect.name == "postgresql":
        conflicts = ", ".join(conflict_columns)
        return (
            f"INSERT INTO {table} ({column_list}) VALUES ({value_list}) "
            f"ON CONFLICT ({conflicts}) DO NOTHING"
        )
    return f"INSERT OR IGNORE INTO {table} ({column_list}) VALUES ({value_list})"


def _areas_aggregate_sql() -> str:
    if ENGINE.dialect.name == "postgresql":
        return "string_agg(DISTINCT a.name, ',')"
    return "GROUP_CONCAT(DISTINCT a.name)"


# ── Areas ─────────────────────────────────────────────────────────────────────

def get_all_areas() -> list[str]:
    rows = _fetch_all("SELECT name FROM areas ORDER BY name")
    return [row["name"] for row in rows]


# ── Categories ────────────────────────────────────────────────────────────────

def get_all_categories() -> list[dict]:
    return _fetch_all("SELECT id, name, group_name FROM categories ORDER BY group_name, id")


def get_supplier_categories(supplier_id: int) -> list[dict]:
    return _fetch_all(
        """SELECT c.id, c.name, c.group_name
           FROM categories c
           JOIN supplier_categories sc ON sc.category_id = c.id
           WHERE sc.supplier_id = :supplier_id
           ORDER BY c.group_name, c.id""",
        {"supplier_id": supplier_id},
    )


def set_supplier_categories(supplier_id: int, category_ids: list[int]):
    with _begin() as conn:
        conn.execute(
            text("DELETE FROM supplier_categories WHERE supplier_id = :supplier_id"),
            {"supplier_id": supplier_id},
        )
        insert_sql = _insert_ignore_sql(
            "supplier_categories",
            ["supplier_id", "category_id"],
            ["supplier_id", "category_id"],
        )
        for cat_id in category_ids:
            conn.execute(text(insert_sql), {"supplier_id": supplier_id, "category_id": cat_id})


# ── Suppliers ─────────────────────────────────────────────────────────────────

def get_suppliers(area: str = None, supplier_type: str = None) -> list[dict]:
    query = """
        SELECT DISTINCT s.id, s.name, s.type, s.website, s.phone,
                        s.email, s.price_band, s.notes, s.address, s.created_at,
                        ROUND(AVG(r.rating), 1) as avg_rating,
                        COUNT(r.id) as review_count
        FROM suppliers s
        LEFT JOIN supplier_areas sa ON sa.supplier_id = s.id
        LEFT JOIN areas a ON a.id = sa.area_id
        LEFT JOIN reviews r ON r.supplier_id = s.id
        WHERE 1=1
    """
    params: dict[str, str] = {}
    if area:
        query += " AND a.name = :area"
        params["area"] = area
    if supplier_type:
        query += " AND s.type = :supplier_type"
        params["supplier_type"] = supplier_type
    query += """
        GROUP BY s.id, s.name, s.type, s.website, s.phone,
                 s.email, s.price_band, s.notes, s.address, s.created_at
        ORDER BY s.name
    """

    return _fetch_all(query, params)


def get_supplier_by_id(supplier_id: int) -> dict | None:
    return _fetch_one(
        """SELECT s.id, s.name, s.type, s.website, s.phone,
                  s.email, s.price_band, s.notes, s.address, s.latitude, s.longitude,
                  pa.name AS primary_area,
                  ROUND(AVG(r.rating), 1) as avg_rating,
                  COUNT(r.id) as review_count
           FROM suppliers s
           LEFT JOIN areas pa ON pa.id = s.primary_area_id
           LEFT JOIN reviews r ON r.supplier_id = s.id
           WHERE s.id = :supplier_id
           GROUP BY s.id, s.name, s.type, s.website, s.phone,
                    s.email, s.price_band, s.notes, s.address, s.latitude, s.longitude, pa.name""",
        {"supplier_id": supplier_id},
    )


def add_supplier(name, supplier_type, website, phone, email,
                      price_band, notes, area_names: list[str],
                      latitude: float | None = None, longitude: float | None = None,
                      address: str | None = None) -> int:
    with _begin() as conn:
        supplier_id = _insert_returning_id(
            conn,
            """INSERT INTO suppliers (name, type, website, phone, email, price_band, notes, address, latitude, longitude)
                VALUES (:name, :supplier_type, :website, :phone, :email, :price_band, :notes, :address, :latitude, :longitude)""",
            {
                "name": name,
                "supplier_type": supplier_type,
                "website": website,
                "phone": phone,
                "email": email,
                "price_band": price_band,
                "notes": notes,
                "address": address,
                "latitude": latitude,
                "longitude": longitude,
            },
        )
        insert_sql = _insert_ignore_sql(
            "supplier_areas",
            ["supplier_id", "area_id"],
            ["supplier_id", "area_id"],
        )
        for area_name in area_names:
            row = conn.execute(
                text("SELECT id FROM areas WHERE name = :area_name"),
                {"area_name": area_name},
            ).mappings().first()
            if row:
                conn.execute(text(insert_sql), {"supplier_id": supplier_id, "area_id": row["id"]})
    return supplier_id


def patch_supplier(supplier_id: int, updates: dict):
    allowed_columns = {
        "name", "type", "website", "phone", "email", "price_band", "notes",
        "address", "latitude", "longitude", "primary_area_id", "trade",
    }
    invalid = set(updates) - allowed_columns
    if invalid:
        raise ValueError(f"Unsupported supplier columns: {sorted(invalid)}")

    assignments = []
    params = {"supplier_id": supplier_id}
    for index, (column, value) in enumerate(updates.items()):
        value_key = f"value_{index}"
        assignments.append(f"{column} = :{value_key}")
        params[value_key] = value

    with _begin() as conn:
        conn.execute(
            text(f"UPDATE suppliers SET {', '.join(assignments)} WHERE id = :supplier_id"),
            params,
        )


def delete_supplier(supplier_id: int):
    with _begin() as conn:
        conn.execute(text("DELETE FROM suppliers WHERE id = :supplier_id"), {"supplier_id": supplier_id})


def get_supplier_areas(supplier_id: int) -> list[str]:
    rows = _fetch_all(
        """SELECT a.name FROM areas a
           JOIN supplier_areas sa ON sa.area_id = a.id
           WHERE sa.supplier_id = :supplier_id""",
        {"supplier_id": supplier_id},
    )
    return [row["name"] for row in rows]


def get_suppliers_with_coords(area: str = None, supplier_type: str = None) -> list[dict]:
    query = """
        SELECT s.id, s.name, s.type, s.trade, s.website, s.phone,
               s.address, s.latitude, s.longitude,
               ROUND(AVG(r.rating), 1) as avg_rating,
               COUNT(r.id) as review_count,
               {areas_aggregate} as areas_csv
        FROM suppliers s
        LEFT JOIN supplier_areas sa ON sa.supplier_id = s.id
        LEFT JOIN areas a ON a.id = sa.area_id
        LEFT JOIN reviews r ON r.supplier_id = s.id
        WHERE s.latitude IS NOT NULL AND s.longitude IS NOT NULL
    """.format(areas_aggregate=_areas_aggregate_sql())
    params: dict[str, str] = {}
    if area:
        query += " AND a.name = :area"
        params["area"] = area
    if supplier_type:
        query += " AND s.type = :supplier_type"
        params["supplier_type"] = supplier_type
    query += """
        GROUP BY s.id, s.name, s.type, s.trade, s.website, s.phone,
                 s.address, s.latitude, s.longitude
        ORDER BY s.name
    """

    rows = _fetch_all(query, params)
    result = []
    for d in rows:
        d['areas'] = d.pop('areas_csv').split(',') if d.get('areas_csv') else []
        result.append(d)
    return result


def get_suppliers_near(lat: float, lon: float, radius_miles: float,
                       supplier_type: str = None) -> list[dict]:
    lat_delta = radius_miles / 69.0
    lon_delta = radius_miles / (69.0 * math.cos(math.radians(lat)))

    query = """
        SELECT s.id, s.name, s.type, s.trade, s.website, s.phone,
             s.address, s.latitude, s.longitude,
               ROUND(AVG(r.rating), 1) as avg_rating,
               COUNT(r.id) as review_count
        FROM suppliers s
        LEFT JOIN reviews r ON r.supplier_id = s.id
                WHERE s.latitude  BETWEEN :min_lat AND :max_lat
                    AND s.longitude BETWEEN :min_lon AND :max_lon
    """
    params: dict[str, float | str] = {
        "min_lat": lat - lat_delta,
        "max_lat": lat + lat_delta,
        "min_lon": lon - lon_delta,
        "max_lon": lon + lon_delta,
    }
    if supplier_type:
        query += " AND s.type = :supplier_type"
        params["supplier_type"] = supplier_type
    query += """
        GROUP BY s.id, s.name, s.type, s.trade, s.website, s.phone,
                 s.address, s.latitude, s.longitude
    """

    return _fetch_all(query, params)


# ── Designers ─────────────────────────────────────────────────────────────────

def get_all_designers() -> list[dict]:
    return _fetch_all("SELECT id, name, company FROM designers ORDER BY name")


def add_designer(name: str, email: str, company: str = None) -> int:
    with _begin() as conn:
        return _insert_returning_id(
            conn,
            "INSERT INTO designers (name, email, company) VALUES (:name, :email, :company)",
            {"name": name, "email": email, "company": company or None},
        )


# ── Reviews ───────────────────────────────────────────────────────────────────

def get_reviews_for_supplier(supplier_id: int) -> list[dict]:
    return _fetch_all(
        """SELECT r.rating, r.review_text, r.job_area, r.created_at,
                  d.name AS designer, d.company AS designer_company
           FROM reviews r
           JOIN designers d ON d.id = r.designer_id
           WHERE r.supplier_id = :supplier_id
           ORDER BY r.created_at DESC""",
        {"supplier_id": supplier_id},
    )


def add_review(supplier_id: int, designer_id: int,
               rating: int, review_text: str, job_area: str):
    with _begin() as conn:
        conn.execute(
            text(
                """INSERT INTO reviews (supplier_id, designer_id, rating, review_text, job_area)
                   VALUES (:supplier_id, :designer_id, :rating, :review_text, :job_area)"""
            ),
            {
                "supplier_id": supplier_id,
                "designer_id": designer_id,
                "rating": rating,
                "review_text": review_text,
                "job_area": job_area or None,
            },
        )
