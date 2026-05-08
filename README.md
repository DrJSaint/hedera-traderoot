# Hedera TradeRoot

Trade supplier directory for garden designers in South East England.

The live app is a FastAPI backend with a vanilla JS and Leaflet frontend. The data is curated county by county through a pipeline that searches, enriches, reviews, imports, audits, and border-tags suppliers before they appear in the main directory.

## Stack

- FastAPI for API routes and static file serving
- PostgreSQL for the live app database
- SQLite for the staging pipeline database (`database/pipeline.db`)
- Alembic for live schema migrations
- Vanilla JS plus Leaflet for the frontend
- Postcodes.io for postcode geocoding
- Google Places plus Anthropic for the sourcing pipeline

## Local setup

Install dependencies:

```bash
pip install -r requirements.txt
```

Set a live database URL. If unset, the app defaults to the legacy local SQLite file at `database/traderoot.db`.

Examples:

```powershell
$env:DATABASE_URL = "postgresql://postgres:<password>@localhost:5432/traderoot"
```

```powershell
$env:DATABASE_URL = "sqlite:///C:/Projects/hedera-traderoot/database/traderoot.db"
```

Apply the live schema:

```bash
alembic upgrade head
```

Optional: load the current local SQLite live data into the configured target database:

```bash
python scripts/migrate_live_data.py
```

Run the app:

```bash
uvicorn app.main:app --reload --port 8000
```

Then open <http://localhost:8000>.

To test on another device on the same network:

```bash
uvicorn app.main:app --reload --port 8000 --host 0.0.0.0
```

## Project layout

```text
hedera-traderoot/
├── app/
│   ├── main.py
│   └── db.py
├── database/
│   ├── schema.sql
│   ├── init_db.py
│   ├── traderoot.db
│   ├── backups/
│   └── archive/
├── scripts/
│   ├── migrate_add_categories.py
│   ├── migrate_add_company.py
│   ├── migrate_add_coords_index.py
│   └── pipeline/
│       ├── 01_search.py
│       ├── 02_enrich.py
│       ├── 02b_trade_review.py
│       ├── 03_review.py
│       ├── 04_import.py
│       ├── audit_county.py
│       ├── county_config.py
│       ├── staging_db.py
│       └── tag_border_suppliers.py
└── static/
    ├── index.html
    ├── app.js
    ├── style.css
    └── images/
```

## Core app model

- `suppliers` stores the main supplier records, including coordinates, `trade`, and `primary_area_id`.
- `areas` plus `supplier_areas` allow a supplier to appear in multiple counties.
- `categories` plus `supplier_categories` store Living and Non-living tags.
- `designers` and `reviews` support peer reviews.
- `offcuts` is a soft archive for suppliers removed during county audits.

The API layer lives in `app/main.py` and the SQL access layer lives in `app/db.py`.

## Database truth

- The live app database is configured by `DATABASE_URL`.
- Alembic migrations in `alembic/versions/` are the source of truth for the live schema.
- `database/pipeline.db` remains a separate SQLite staging database for the search/enrich/review pipeline.
- `database/schema.sql` is a SQLite reference snapshot of the current live schema, not the migration authority.
- `database/init_db.py` is a convenience bootstrap for creating an empty local SQLite live database via Alembic plus seed lookup data.

## County pipeline

Run the pipeline in this order for each county:

```bash
python scripts/pipeline/01_search.py "East Sussex"
python scripts/pipeline/02_enrich.py "East Sussex"
python scripts/pipeline/02b_trade_review.py "East Sussex"
python scripts/pipeline/03_review.py "East Sussex"
python scripts/pipeline/03_review.py approve "East Sussex"
python scripts/pipeline/04_import.py "East Sussex"
python scripts/pipeline/audit_county.py "East Sussex" --apply
python scripts/pipeline/tag_border_suppliers.py --apply
```

To re-run enrichment for a county:

```bash
python scripts/pipeline/reset_county.py "East Sussex"
```

Key pipeline files:

- `scripts/pipeline/staging_db.py` manages the SQLite staging database.
- `scripts/pipeline/04_import.py` writes approved pipeline rows into the live database configured by `DATABASE_URL`.
- `scripts/pipeline/audit_county.py` and `scripts/pipeline/audit_surrey.py` move out-of-county suppliers into `offcuts`.
- `scripts/pipeline/tag_border_suppliers.py` adds secondary county tags and recalculates `primary_area_id`.

## Required environment variables for the pipeline

```powershell
$env:GOOGLE_PLACES_KEY = "..."
$env:ANTHROPIC_API_KEY = "..."
```

Without those keys, the web app can still run against an existing local database, but the sourcing pipeline cannot fetch or enrich new suppliers.

## Current data notes

- Surrey: 93 suppliers
- West Sussex: 95 suppliers
- East Sussex: imported
- Border suppliers can belong to multiple counties
- `primary_area_id` reflects the supplier's actual county location, not just the search county that found it

## Important design choices

- County imports are clean replaces, not additive merges, when a county is supplied to `04_import.py`.
- SQLite backups are written to `database/backups/` before each import only when the live DB is a local SQLite file.
- Audit scripts move removed suppliers into `offcuts` instead of hard-deleting them.
- Border tagging recalculates `primary_area_id` using the nearest configured county centre.
- All frontend filtering is client-side after `/api/map` loads the supplier set.
