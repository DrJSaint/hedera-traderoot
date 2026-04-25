-- Hedera TradeRoot Database Schema
-- Garden design trade supplier directory for South East England

CREATE TABLE IF NOT EXISTS areas (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE  -- e.g. Kent, Surrey, East Sussex
);

CREATE TABLE IF NOT EXISTS suppliers (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    type        TEXT NOT NULL,        -- nursery | hard_landscaper | furniture | lighting | tools | other
    website     TEXT,
    phone       TEXT,
    email       TEXT,
    price_band  TEXT,                 -- budget | mid | premium
    notes       TEXT,
    latitude    REAL,                 -- nullable, for v2 map feature
    longitude   REAL,                 -- nullable, for v2 map feature
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS supplier_areas (
    supplier_id INTEGER NOT NULL REFERENCES suppliers(id) ON DELETE CASCADE,
    area_id     INTEGER NOT NULL REFERENCES areas(id) ON DELETE CASCADE,
    PRIMARY KEY (supplier_id, area_id)
);

CREATE TABLE IF NOT EXISTS designers (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    email       TEXT UNIQUE NOT NULL,
    company     TEXT,
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_suppliers_lat_lon
    ON suppliers(latitude, longitude);

CREATE TABLE IF NOT EXISTS reviews (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    supplier_id INTEGER NOT NULL REFERENCES suppliers(id) ON DELETE CASCADE,
    designer_id INTEGER NOT NULL REFERENCES designers(id) ON DELETE CASCADE,
    rating      INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
    review_text TEXT,
    job_area    TEXT,                 -- the county where the job was, free text for now
    created_at  TEXT DEFAULT (datetime('now'))
);
