# Hedera TradeRoot — Claude context

Trade supplier directory for garden designers in South East England.
Started as a Streamlit + HTA scrape prototype; fully rebuilt with a
proper data pipeline and clean dataset.

## Stack

- **FastAPI** — API + static file serving (`app/main.py`)
- **SQLite** (`database/traderoot.db`) — all data; accessed via `app/db.py`
- **Vanilla JS + Leaflet.js** — frontend (`static/app.js`, `static/index.html`)
- **Python pipeline** — `scripts/pipeline/` — sourcing, enriching, reviewing, importing suppliers

## Running the app

```bash
uvicorn app.main:app --reload --port 8000
```

## Database schema

| Table | Purpose |
|---|---|
| `suppliers` | Core supplier records. Key fields: `name`, `type`, `website`, `phone`, `latitude`, `longitude`, `primary_area_id`, `trade` (1 = does trade accounts, 0 = retail only) |
| `areas` | UK counties (Surrey id=3, West Sussex id=5, East Sussex id=4, Kent id=2, Hampshire id=9) |
| `supplier_areas` | Many-to-many supplier ↔ area (a supplier can belong to multiple counties) |
| `categories` | Supply categories (Living / Non-living) |
| `supplier_categories` | Many-to-many supplier ↔ category |
| `designers` | Garden designers who leave reviews |
| `reviews` | Ratings + text reviews |
| `offcuts` | Soft-archive of suppliers removed during county audits |

`suppliers.primary_area_id` — the county the supplier *actually* sits in
(may differ from which pipeline search found them, e.g. a West Sussex
search can surface a supplier whose address is East Sussex).

## Supplier types

`nursery`, `garden_centre`, `hard_landscaper`, `soils_aggregates`,
`timber`, `furniture`, `tools`, `lighting`, `other`

## Data pipeline (`scripts/pipeline/`)

Run in order for each new county:

```
01_search.py   "East Sussex"   # Google Places text search → pipeline.db (raw_places)
02_enrich.py   "East Sussex"   # Claude Haiku classification → pipeline.db (enriched)
03_review.py   "East Sussex"   # HTML report to reports/; approve with 'approve' arg
03_review.py approve "East Sussex"
04_import.py   "East Sussex"   # Clean-replaces county in traderoot.db (auto-backup first)
audit_county.py "East Sussex"          # Report only
audit_county.py "East Sussex" --apply  # Move non-county suppliers to offcuts
tag_border_suppliers.py                # Dry run
tag_border_suppliers.py --apply        # Tag border suppliers to neighbouring counties
                                       # + recalculates primary_area_id
```

Key files:
- `staging_db.py` — pipeline.db schema + connection
- `county_config.py` — lat/lon centre, bounding box, postcode regex per county
- `04_import.py` — does a **clean replace** (not additive merge) when county is given

## County config (`county_config.py`)

Each county has: `lat/lon` (search bias centre), `radius_m`, `bounds`
(bounding box for address filtering), `signals` (postcode regex fallback).

Configured: Surrey, West Sussex, East Sussex, Kent, Hampshire.

Surrey special case: its bounding box overlaps Greater London, so a
postcode signals check is also required (not just lat/lon in bounds).

## Current data

- **Surrey** — 93 suppliers (pipeline-verified)
- **West Sussex** — 95 suppliers (pipeline-verified, clean replace)
- Total: 188 suppliers; all have lat/lon; no duplicates
- HTA scrape data removed entirely (archived at `database/archive/traderoot_hta_scrape_archive.db`)
- Border suppliers (e.g. Uckfield/Hailsham suppliers found via WS search)
  are tagged to both counties; `primary_area_id` reflects actual location

## Next counties to run

East Sussex → Kent → Hampshire (run pipeline stages in order above)

## Env vars needed for pipeline

```powershell
$env:GOOGLE_PLACES_KEY = "..."   # Google Places API key
$env:ANTHROPIC_API_KEY = "..."   # Claude API key (Haiku used for enrichment)
```

## Key design decisions

- **Clean replace on import**: `04_import.py <county>` deletes all
  existing suppliers for that county before inserting pipeline results.
  Backup is written to `database/backups/` before each import.
- **Offcuts table**: non-county suppliers are never hard-deleted;
  `audit_county.py --apply` moves them to `offcuts` with a reason tag.
- **Border tagging**: `tag_border_suppliers.py` uses bounding box overlap
  to find suppliers that sit in multiple counties and adds secondary
  `supplier_areas` links. `primary_area_id` is recalculated to the
  county whose config centre is closest to the supplier's lat/lon.
- **Surrey/London overlap**: Surrey's bounding box covers part of Greater
  London; always requires postcode signals match in addition to lat/lon.
