"""
Database access layer for Hedera TradeRoot.
All SQL lives here — main.py should only call these functions.
"""

import sqlite3
import pandas as pd

DB_PATH = "database/traderoot.db"


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


# ── Suppliers ─────────────────────────────────────────────────────────────────

def get_suppliers(area: str = None, supplier_type: str = None) -> pd.DataFrame:
    query = """
        SELECT DISTINCT s.id, s.name, s.type, s.website, s.phone,
                        s.email, s.price_band, s.notes, s.created_at
        FROM suppliers s
        LEFT JOIN supplier_areas sa ON sa.supplier_id = s.id
        LEFT JOIN areas a ON a.id = sa.area_id
        WHERE 1=1
    """
    params = []
    if area:
        query += " AND a.name = ?"
        params.append(area)
    if supplier_type:
        query += " AND s.type = ?"
        params.append(supplier_type)
    query += " ORDER BY s.name"

    with get_connection() as conn:
        return pd.read_sql_query(query, conn, params=params)


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


# ── Designers ─────────────────────────────────────────────────────────────────

def get_all_designers() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, name FROM designers ORDER BY name"
        ).fetchall()
    return [dict(r) for r in rows]


def add_designer(name: str, email: str) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO designers (name, email) VALUES (?, ?)",
            (name, email)
        )
        conn.commit()
    return cur.lastrowid


# ── Reviews ───────────────────────────────────────────────────────────────────

def get_reviews_for_supplier(supplier_id: int) -> pd.DataFrame:
    query = """
        SELECT r.rating, r.review_text, r.job_area, r.created_at,
               d.name AS designer
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


# ── Map ───────────────────────────────────────────────────────────────────────

def get_suppliers_with_coords(area: str = None, supplier_type: str = None) -> pd.DataFrame:
    """Return only suppliers that have lat/long coordinates."""
    query = """
        SELECT DISTINCT s.id, s.name, s.type, s.website, s.phone,
                        s.email, s.price_band, s.notes,
                        s.latitude, s.longitude
        FROM suppliers s
        LEFT JOIN supplier_areas sa ON sa.supplier_id = s.id
        LEFT JOIN areas a ON a.id = sa.area_id
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
    query += " ORDER BY s.name"

    with get_connection() as conn:
        return pd.read_sql_query(query, conn, params=params)


def get_all_suppliers_with_coords() -> pd.DataFrame:
    """Return ALL suppliers with coordinates for proximity search."""
    query = """
        SELECT DISTINCT s.id, s.name, s.type, s.website, s.phone,
                        s.email, s.notes, s.latitude, s.longitude
        FROM suppliers s
        WHERE s.latitude IS NOT NULL
          AND s.longitude IS NOT NULL
        ORDER BY s.name
    """
    with get_connection() as conn:
        return pd.read_sql_query(query, conn)
