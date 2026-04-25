"""
Database access layer for Hedera TradeRoot.
All SQL lives here — main.py should only call these functions.
"""

import math
import os
import sqlite3
import pandas as pd

DB_PATH = os.path.normpath(
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "database", "traderoot.db")
)


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# ── Areas ─────────────────────────────────────────────────────────────────────

def get_all_areas() -> list[str]:
    with get_connection() as conn:
        rows = conn.execute("SELECT name FROM areas ORDER BY name").fetchall()
    return [r["name"] for r in rows]


# ── Categories ────────────────────────────────────────────────────────────────

def get_all_categories() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, name, group_name FROM categories ORDER BY group_name, id"
        ).fetchall()
    return [dict(r) for r in rows]


def get_supplier_categories(supplier_id: int) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT c.id, c.name, c.group_name
               FROM categories c
               JOIN supplier_categories sc ON sc.category_id = c.id
               WHERE sc.supplier_id = ?
               ORDER BY c.group_name, c.id""",
            (supplier_id,)
        ).fetchall()
    return [dict(r) for r in rows]


def set_supplier_categories(supplier_id: int, category_ids: list[int]):
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM supplier_categories WHERE supplier_id = ?",
            (supplier_id,)
        )
        for cat_id in category_ids:
            conn.execute(
                "INSERT OR IGNORE INTO supplier_categories (supplier_id, category_id) VALUES (?, ?)",
                (supplier_id, cat_id)
            )
        conn.commit()


# ── Suppliers ─────────────────────────────────────────────────────────────────

def get_suppliers(area: str = None, supplier_type: str = None) -> pd.DataFrame:
    query = """
        SELECT DISTINCT s.id, s.name, s.type, s.website, s.phone,
                        s.email, s.price_band, s.notes, s.created_at,
                        ROUND(AVG(r.rating), 1) as avg_rating,
                        COUNT(r.id) as review_count
        FROM suppliers s
        LEFT JOIN supplier_areas sa ON sa.supplier_id = s.id
        LEFT JOIN areas a ON a.id = sa.area_id
        LEFT JOIN reviews r ON r.supplier_id = s.id
        WHERE 1=1
    """
    params = []
    if area:
        query += " AND a.name = ?"
        params.append(area)
    if supplier_type:
        query += " AND s.type = ?"
        params.append(supplier_type)
    query += " GROUP BY s.id ORDER BY s.name"

    with get_connection() as conn:
        return pd.read_sql_query(query, conn, params=params)


def get_supplier_by_id(supplier_id: int) -> dict:
    with get_connection() as conn:
        row = conn.execute(
            """SELECT s.id, s.name, s.type, s.website, s.phone,
                      s.email, s.price_band, s.notes,
                      ROUND(AVG(r.rating), 1) as avg_rating,
                      COUNT(r.id) as review_count
               FROM suppliers s
               LEFT JOIN reviews r ON r.supplier_id = s.id
               WHERE s.id = ?
               GROUP BY s.id""",
            (supplier_id,)
        ).fetchone()
    return dict(row) if row else None


def add_supplier(name, supplier_type, website, phone, email,
                 price_band, notes, area_names: list[str]) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            """INSERT INTO suppliers (name, type, website, phone, email, price_band, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (name, supplier_type, website, phone, email, price_band, notes)
        )
        supplier_id = cur.lastrowid

        for area_name in area_names:
            row = conn.execute(
                "SELECT id FROM areas WHERE name = ?", (area_name,)
            ).fetchone()
            if row:
                conn.execute(
                    "INSERT OR IGNORE INTO supplier_areas (supplier_id, area_id) VALUES (?, ?)",
                    (supplier_id, row["id"])
                )
        conn.commit()
    return supplier_id


def delete_supplier(supplier_id: int):
    with get_connection() as conn:
        conn.execute("DELETE FROM suppliers WHERE id = ?", (supplier_id,))
        conn.commit()


def get_supplier_areas(supplier_id: int) -> list[str]:
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT a.name FROM areas a
               JOIN supplier_areas sa ON sa.area_id = a.id
               WHERE sa.supplier_id = ?""",
            (supplier_id,)
        ).fetchall()
    return [r["name"] for r in rows]


def get_suppliers_with_coords(area: str = None, supplier_type: str = None) -> pd.DataFrame:
    query = """
        SELECT DISTINCT s.id, s.name, s.type, s.website, s.phone,
                        s.email, s.price_band, s.notes,
                        s.latitude, s.longitude,
                        ROUND(AVG(r.rating), 1) as avg_rating,
                        COUNT(r.id) as review_count
        FROM suppliers s
        LEFT JOIN supplier_areas sa ON sa.supplier_id = s.id
        LEFT JOIN areas a ON a.id = sa.area_id
        LEFT JOIN reviews r ON r.supplier_id = s.id
        WHERE s.latitude IS NOT NULL
          AND s.longitude IS NOT NULL
    """
    params = []
    if area:
        query += " AND a.name = ?"
        params.append(area)
    if supplier_type:
        query += " AND s.type = ?"
        params.append(supplier_type)
    query += " GROUP BY s.id ORDER BY s.name"

    with get_connection() as conn:
        return pd.read_sql_query(query, conn, params=params)


def get_all_suppliers_with_coords() -> pd.DataFrame:
    query = """
        SELECT DISTINCT s.id, s.name, s.type, s.website, s.phone,
                        s.email, s.notes, s.latitude, s.longitude,
                        ROUND(AVG(r.rating), 1) as avg_rating,
                        COUNT(r.id) as review_count
        FROM suppliers s
        LEFT JOIN reviews r ON r.supplier_id = s.id
        WHERE s.latitude IS NOT NULL
          AND s.longitude IS NOT NULL
        GROUP BY s.id
        ORDER BY s.name
    """
    with get_connection() as conn:
        return pd.read_sql_query(query, conn)


def get_suppliers_near(lat: float, lon: float, radius_miles: float,
                       supplier_type: str = None) -> pd.DataFrame:
    """Return suppliers within a bounding box, ready for exact haversine filtering."""
    lat_delta = radius_miles / 69.0
    lon_delta = radius_miles / (69.0 * math.cos(math.radians(lat)))

    query = """
        SELECT s.id, s.name, s.type, s.website, s.phone,
               s.email, s.notes, s.latitude, s.longitude,
               ROUND(AVG(r.rating), 1) as avg_rating,
               COUNT(r.id) as review_count
        FROM suppliers s
        LEFT JOIN reviews r ON r.supplier_id = s.id
        WHERE s.latitude  BETWEEN ? AND ?
          AND s.longitude BETWEEN ? AND ?
    """
    params: list = [
        lat - lat_delta, lat + lat_delta,
        lon - lon_delta, lon + lon_delta,
    ]

    if supplier_type:
        query += " AND s.type = ?"
        params.append(supplier_type)

    query += " GROUP BY s.id"

    with get_connection() as conn:
        return pd.read_sql_query(query, conn, params=params)


# ── Designers ─────────────────────────────────────────────────────────────────

def get_all_designers() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, name, company FROM designers ORDER BY name"
        ).fetchall()
    return [dict(r) for r in rows]


def add_designer(name: str, email: str, company: str = None) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO designers (name, email, company) VALUES (?, ?, ?)",
            (name, email, company or None)
        )
        conn.commit()
    return cur.lastrowid


# ── Reviews ───────────────────────────────────────────────────────────────────

def get_reviews_for_supplier(supplier_id: int) -> pd.DataFrame:
    query = """
        SELECT r.rating, r.review_text, r.job_area, r.created_at,
               d.name AS designer,
               d.company AS designer_company
        FROM reviews r
        JOIN designers d ON d.id = r.designer_id
        WHERE r.supplier_id = ?
        ORDER BY r.created_at DESC
    """
    with get_connection() as conn:
        return pd.read_sql_query(query, conn, params=(supplier_id,))


def add_review(supplier_id: int, designer_id: int,
               rating: int, review_text: str, job_area: str):
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO reviews (supplier_id, designer_id, rating, review_text, job_area)
               VALUES (?, ?, ?, ?, ?)""",
            (supplier_id, designer_id, rating, review_text, job_area)
        )
        conn.commit()
