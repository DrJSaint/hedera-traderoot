"""Copy live TradeRoot data from the local SQLite database into the configured target DB.

Usage:
    python scripts/migrate_live_data.py

The source is always the current local SQLite file unless overridden with
--source. The target comes from DATABASE_URL via app.live_db.
"""

import argparse
import os
import sqlite3
import sys
from pathlib import Path

from sqlalchemy import text

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database_config import DEFAULT_SQLITE_PATH, get_sqlite_db_path
from app.live_db import get_engine


TABLE_ORDER = [
    "areas",
    "categories",
    "designers",
    "suppliers",
    "supplier_areas",
    "supplier_categories",
    "reviews",
    "offcuts",
]


INSERT_SQL = {
    "areas": text("INSERT INTO areas (id, name) VALUES (:id, :name)"),
    "categories": text(
        "INSERT INTO categories (id, name, group_name) VALUES (:id, :name, :group_name)"
    ),
    "designers": text(
        "INSERT INTO designers (id, name, email, company, created_at) "
        "VALUES (:id, :name, :email, :company, :created_at)"
    ),
    "suppliers": text(
        "INSERT INTO suppliers ("
        "id, name, type, website, phone, email, price_band, notes, latitude, longitude, "
        "created_at, primary_area_id, trade, address"
        ") VALUES ("
        ":id, :name, :type, :website, :phone, :email, :price_band, :notes, :latitude, :longitude, "
        ":created_at, :primary_area_id, :trade, :address"
        ")"
    ),
    "supplier_areas": text(
        "INSERT INTO supplier_areas (supplier_id, area_id) VALUES (:supplier_id, :area_id)"
    ),
    "supplier_categories": text(
        "INSERT INTO supplier_categories (supplier_id, category_id) VALUES (:supplier_id, :category_id)"
    ),
    "reviews": text(
        "INSERT INTO reviews (id, supplier_id, designer_id, rating, review_text, job_area, created_at) "
        "VALUES (:id, :supplier_id, :designer_id, :rating, :review_text, :job_area, :created_at)"
    ),
    "offcuts": text(
        "INSERT INTO offcuts ("
        "id, original_id, name, type, website, phone, email, price_band, notes, latitude, longitude, "
        "address, offcut_reason, inferred_area, archived_at, original_county"
        ") VALUES ("
        ":id, :original_id, :name, :type, :website, :phone, :email, :price_band, :notes, :latitude, :longitude, "
        ":address, :offcut_reason, :inferred_area, :archived_at, :original_county"
        ")"
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default=str(DEFAULT_SQLITE_PATH), help="Path to source SQLite DB")
    return parser.parse_args()


def load_source_rows(source_path: Path) -> dict[str, list[dict]]:
    conn = sqlite3.connect(source_path)
    conn.row_factory = sqlite3.Row
    data = {}
    try:
        for table in TABLE_ORDER:
            rows = conn.execute(f"SELECT * FROM {table} ORDER BY 1").fetchall()
            data[table] = [dict(row) for row in rows]
    finally:
        conn.close()
    return data


def reset_target(connection) -> None:
    if connection.dialect.name == "postgresql":
        connection.execute(
            text(
                "TRUNCATE TABLE offcuts, reviews, supplier_categories, supplier_areas, suppliers, designers, categories, areas "
                "RESTART IDENTITY CASCADE"
            )
        )
        return

    for table in reversed(TABLE_ORDER):
        connection.execute(text(f"DELETE FROM {table}"))

    if connection.dialect.name == "sqlite":
        sqlite_sequence_exists = connection.execute(
            text("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'sqlite_sequence'")
        ).scalar()
        if sqlite_sequence_exists:
            connection.execute(
                text(
                    "DELETE FROM sqlite_sequence WHERE name IN "
                    "('areas', 'categories', 'designers', 'suppliers', 'reviews', 'offcuts')"
                )
            )


def sync_sequences(connection) -> None:
    if connection.dialect.name != "postgresql":
        return

    sequence_map = {
        "areas": "id",
        "categories": "id",
        "designers": "id",
        "suppliers": "id",
        "reviews": "id",
        "offcuts": "id",
    }
    for table, column in sequence_map.items():
        connection.execute(
            text(
                "SELECT setval(pg_get_serial_sequence(:table_name, :column_name), "
                "COALESCE((SELECT MAX(id) FROM " + table + "), 1), true)"
            ),
            {"table_name": table, "column_name": column},
        )


def main() -> None:
    args = parse_args()
    source_path = Path(args.source).resolve()
    target_sqlite_path = get_sqlite_db_path()

    if target_sqlite_path and Path(target_sqlite_path).resolve() == source_path:
        raise SystemExit("Refusing to migrate into the same SQLite database file.")

    rows_by_table = load_source_rows(source_path)
    engine = get_engine()

    with engine.begin() as connection:
        reset_target(connection)
        for table in TABLE_ORDER:
            rows = rows_by_table[table]
            if rows:
                connection.execute(INSERT_SQL[table], rows)
                print(f"Imported {len(rows)} rows into {table}")
            else:
                print(f"Imported 0 rows into {table}")
        sync_sequences(connection)


if __name__ == "__main__":
    main()