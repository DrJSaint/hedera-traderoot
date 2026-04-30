# Hedera TradeRoot — Claude context

Trade supplier directory for garden designers in South East England.
Started as an HTA scrape prototype; fully rebuilt with a
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
| --- | --- |
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

```bash
01_search.py   "East Sussex"          # Google Places text search → pipeline.db (raw_places)
02_enrich.py   "East Sussex"          # Claude Haiku classification → pipeline.db (enriched)
02b_trade_review.py "East Sussex"     # Claude Sonnet second pass — corrects trade flags
03_review.py   "East Sussex"          # HTML report to reports/; approve with 'approve' arg
03_review.py approve "East Sussex"
04_import.py   "East Sussex"          # Clean-replaces county in traderoot.db (auto-backup first)
audit_county.py "East Sussex"          # Report only
audit_county.py "East Sussex" --apply  # Move non-county suppliers to offcuts
tag_border_suppliers.py                # Dry run
tag_border_suppliers.py --apply        # Tag border suppliers to neighbouring counties
                                       # + recalculates primary_area_id
```

To re-run enrichment for a county (e.g. after prompt changes):

```bash
reset_county.py "East Sussex"         # Clears enriched records so 02_enrich re-processes them
```

Key files:

- `staging_db.py` — pipeline.db schema + connection
- `county_config.py` — lat/lon centre, bounding box, postcode regex per county
- `04_import.py` — does a **clean replace** (not additive merge) when county is given

### 02_enrich.py prompt modes

Two prompt modes, selected via flag:

```bash
02_enrich.py "Kent"                  # Default: type-based trade defaults (recommended)
02_enrich.py "Kent" --conservative   # Evidence-only: no type defaults
```

**Type-defaults (default):** nursery, hard_landscaper, soils_aggregates, timber → trade=true
unless website explicitly says retail/public only. garden_centre, furniture, tools, lighting,
other → trade=false unless explicit evidence. Haiku makes fewer errors; Sonnet corrects edge cases.

**Conservative:** No defaults — Haiku must find positive evidence of trade. Produces more
false negatives (and surprisingly more false positives too). Only use for comparison/testing.

### 02b_trade_review.py — Sonnet trade second pass

- Reads all relevant suppliers for the county from staging
- Fetches fresh website text for each
- Asks Sonnet (claude-sonnet-4-6) for a focused trade verdict
- Updates `trade_only` in staging; preserves Haiku's original flag in `trade_only_haiku`
- Reports which suppliers flipped false→true or true→false
- Typical result: ~15–20 flips on a county of 70–80 suppliers

### 03_review.py HTML report

- Flip badges on trade column: green **+trade** (Sonnet upgraded) / red **-trade** (Sonnet downgraded)
- "Sonnet flips" stat card showing total flip count
- Filter dropdown: "Flipped only" to inspect just the corrections

## County config (`county_config.py`)

Each county has: `lat/lon` (search bias centre), `radius_m`, `bounds`
(bounding box for address filtering), `signals` (postcode regex fallback).

Configured: Surrey, West Sussex, East Sussex, Kent, Hampshire.

Surrey special case: its bounding box overlaps Greater London, so a
postcode signals check is also required (not just lat/lon in bounds).

## Current data

- **Surrey** — 93 suppliers (pipeline-verified)
- **West Sussex** — 95 suppliers (pipeline-verified, clean replace)
- **East Sussex** — imported (approved + clean replace done)
- Total live: ~263 suppliers; all have lat/lon; no duplicates
- HTA scrape data removed entirely (archived at `database/archive/traderoot_hta_scrape_archive.db`)
- Border suppliers (e.g. Uckfield/Hailsham suppliers found via WS search)
  are tagged to both counties; `primary_area_id` reflects actual location

## Next steps

1. Audit East Sussex: `audit_county.py "East Sussex" --apply` then `tag_border_suppliers.py --apply`
2. Then Kent → Hampshire (full pipeline from `01_search.py`)

## Frontend (`static/`)

- **Logo**: `static/images/traderoot_logo.png` — 64px height, header background `#172727`
- **Type pills**: multi-select, color-coded dots, active state fills with type colour
- **County filter**: single dropdown (`#map-area-filter`), populated from `/api/areas`
- **Supplier search**: live name filter, clears proximity mode when used
- **Trade only pill**: filters by `suppliers.trade = 1`
- **Proximity search**: postcode or geolocation; resets county/search on activate;
  county/search changes exit proximity mode
- All filtering is **client-side** — all suppliers loaded once on boot via `/api/map`
- To test on tablet/phone on same Wi-Fi: `uvicorn app.main:app --reload --port 8000 --host 0.0.0.0`

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
