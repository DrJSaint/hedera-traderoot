"""
Initialise an empty local SQLite TradeRoot database.
This is a convenience bootstrap for local SQLite only.
The live schema itself is owned by Alembic migrations.

Run once on first SQLite setup: python database/init_db.py
"""

import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy import text

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(ROOT_DIR, "database", "traderoot.db")

AREAS = [
    "London", "Kent", "Surrey", "East Sussex", "West Sussex",
    "Hertfordshire", "Essex", "Berkshire", "Hampshire", "Oxfordshire",
]

CATEGORIES = [
    ("Trees", "Living"),
    ("Shrubs", "Living"),
    ("Perennials", "Living"),
    ("Grasses", "Living"),
    ("Alpine", "Living"),
    ("Hedging", "Living"),
    ("Climbers", "Living"),
    ("Paving", "Non-living"),
    ("Gravel", "Non-living"),
    ("Decking", "Non-living"),
    ("Fencing", "Non-living"),
    ("Trellis", "Non-living"),
    ("Pergola/Arbour", "Non-living"),
]


def build_sqlite_url() -> str:
    return f"sqlite:///{Path(DB_PATH).resolve().as_posix()}"


def apply_schema() -> None:
    alembic_cfg = Config(str(Path(ROOT_DIR) / "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", build_sqlite_url())
    command.upgrade(alembic_cfg, "head")


def init_db():
    if os.path.exists(DB_PATH):
        print(f"Database already exists at {DB_PATH} — skipping init.")
        return DB_PATH

    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    apply_schema()

    engine = create_engine(build_sqlite_url(), future=True, connect_args={"check_same_thread": False})
    with engine.begin() as conn:
        conn.execute(
            text("INSERT OR IGNORE INTO areas (name) VALUES (:name)"),
            [{"name": area} for area in AREAS],
        )
        conn.execute(
            text("INSERT OR IGNORE INTO categories (name, group_name) VALUES (:name, :group_name)"),
            [{"name": name, "group_name": group_name} for name, group_name in CATEGORIES],
        )
        conn.execute(
            text("INSERT OR IGNORE INTO designers (name, email) VALUES (:name, :email)"),
            {"name": "Eleanor", "email": "eleanor@hederagardendesign.co.uk"},
        )

    print(f"Database initialised at {DB_PATH}")
    return DB_PATH


if __name__ == "__main__":
    init_db()
