"""
Shared staging database for the supplier pipeline.
Keeps raw Places data and Claude enrichment separate from traderoot.db
until records are approved.
"""

import os
import sqlite3

STAGING_PATH = os.path.normpath(
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                 "database", "pipeline.db")
)


def get_connection():
    conn = sqlite3.connect(STAGING_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS raw_places (
                place_id    TEXT PRIMARY KEY,
                name        TEXT NOT NULL,
                address     TEXT,
                phone       TEXT,
                website     TEXT,
                lat         REAL,
                lon         REAL,
                google_types TEXT,
                search_term  TEXT,
                search_county TEXT,
                fetched_at  TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS enriched (
                place_id        TEXT PRIMARY KEY REFERENCES raw_places(place_id),
                relevant        INTEGER,        -- 1 = yes, 0 = no
                supplier_type   TEXT,
                categories      TEXT,           -- JSON array of category names
                trade_only      INTEGER,        -- 1 = trade, 0 = retail/public (Sonnet-reviewed if 02b run)
                trade_only_haiku INTEGER,       -- original Haiku flag, preserved for comparison
                confidence      REAL,
                notes           TEXT,
                enriched_at     TEXT DEFAULT (datetime('now')),
                approved        INTEGER DEFAULT 0
            );
        """)
        conn.commit()
    return STAGING_PATH
