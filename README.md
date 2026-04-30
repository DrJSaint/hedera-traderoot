# Hedera TradeRoot

Trade supplier directory for garden designers in South East England.

The live app is a FastAPI backend with a vanilla JS and Leaflet frontend. The data is curated county by county through a pipeline that searches, enriches, reviews, imports, audits, and border-tags suppliers before they appear in the main directory.

## Stack

- FastAPI for API routes and static file serving
- SQLite for live and staging databases
- Vanilla JS plus Leaflet for the frontend
- Postcodes.io for postcode geocoding
- Google Places plus Anthropic for the sourcing pipeline

## Local setup

Install dependencies:

```bash
pip install -r requirements.txt
```

Initialise an empty local database if you do not already have one:

```bash
python database/init_db.py
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
- Audit scripts move removed suppliers into `offcuts` instead of hard-deleting them.
- Border tagging recalculates `primary_area_id` using the nearest configured county centre.
- All frontend filtering is client-side after `/api/map` loads the supplier set.
