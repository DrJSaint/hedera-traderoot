# Hedera TradeRoot

Trade supplier directory for garden designers in South East England.
Covers nurseries, hard landscapers, soils & aggregates, timber, furniture,
tools, lighting, and more — with interactive map, postcode proximity search,
and peer reviews from the designer community.

## Stack

- **FastAPI** — API and static file serving
- **SQLite** — database (`database/traderoot.db`)
- **Vanilla JS + Leaflet.js** — frontend (no framework)
- **Postcodes.io** — free UK postcode geocoding

## Running locally

```bash
uvicorn app.main:app --reload --port 8000
```

Then open [http://localhost:8000](http://localhost:8000).

## Project structure

```
hedera-traderoot/
├── app/
│   ├── main.py              # FastAPI routes
│   └── db.py                # Database access layer (all SQL lives here)
├── database/
│   ├── schema.sql           # Database schema
│   ├── traderoot.db         # Live SQLite database
│   ├── backups/             # Auto-backups created before each import
│   └── archive/             # Archived legacy datasets
├── scripts/pipeline/
│   ├── 01_search.py         # Stage 1: Google Places search → staging DB
│   ├── 02_enrich.py         # Stage 2: Claude AI classification
│   ├── 03_review.py         # Stage 3: HTML review report + approval
│   ├── 04_import.py         # Stage 4: Clean import into traderoot.db
│   ├── audit_county.py      # Post-import: move out-of-county to offcuts
│   ├── tag_border_suppliers.py  # Tag border suppliers to neighbouring counties
│   ├── county_config.py     # Bounding boxes + postcode signals per county
│   └── staging_db.py        # Pipeline staging database schema
└── static/
    ├── index.html
    ├── app.js
    └── style.css
```

## Data pipeline

Suppliers are sourced county-by-county using a 4-stage pipeline:

```bash
python scripts/pipeline/01_search.py "East Sussex"     # Google Places → staging DB
python scripts/pipeline/02_enrich.py "East Sussex"     # Claude classifies each result
python scripts/pipeline/03_review.py "East Sussex"     # Review HTML report
python scripts/pipeline/03_review.py approve "East Sussex"
python scripts/pipeline/04_import.py "East Sussex"     # Clean replace into live DB
python scripts/pipeline/audit_county.py "East Sussex" --apply
python scripts/pipeline/tag_border_suppliers.py --apply
```

Requires `GOOGLE_PLACES_KEY` and `ANTHROPIC_API_KEY` environment variables.

## Database schema

| Table | Purpose |
|---|---|
| `suppliers` | Supplier records with `primary_area_id` for display location |
| `areas` | UK counties |
| `supplier_areas` | Many-to-many: supplier ↔ county (border suppliers appear in multiple) |
| `categories` | Supply categories (Living / Non-living) |
| `supplier_categories` | Many-to-many: supplier ↔ category |
| `designers` | Garden designers who leave reviews |
| `reviews` | Star ratings and text reviews |
| `offcuts` | Soft-archive of suppliers removed during county audits |

## Current coverage

| County | Suppliers |
|---|---|
| Surrey | 93 |
| West Sussex | 95 |
