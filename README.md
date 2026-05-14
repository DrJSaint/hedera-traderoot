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
├── alembic/
│   ├── env.py
│   └── versions/
├── alembic.ini
├── Procfile
├── app/
│   ├── admin_routes.py
│   ├── auth.py
│   ├── auth_routes.py
│   ├── database_config.py
│   ├── db.py
│   ├── live_db.py
│   ├── main.py
│   └── request_routes.py
├── database/
│   ├── schema.sql
│   ├── init_db.py
│   ├── pipeline.db
│   ├── traderoot.db
│   ├── backups/
│   └── archive/
├── scripts/
│   ├── create_admin.py
│   ├── migrate_live_data.py
│   ├── reset_password.py
│   └── pipeline/
│       ├── 01_search.py
│       ├── 02_enrich.py
│       ├── 02b_trade_review.py
│       ├── 03_review.py
│       ├── 04_import.py
│       ├── audit_county.py
│       ├── audit_surrey.py
│       ├── county_config.py
│       ├── live_db_helpers.py
│       ├── offcuts_report.py
│       ├── reset_county.py
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
- `designers` and `reviews` support peer reviews. Reviews are unique per designer per supplier.
- `users` stores login accounts (admin and designer roles), linked to `designers` records.
- `supplier_requests` stores designer-submitted add/edit requests pending admin approval.
- `password_reset_tokens` stores one-time tokens for the forgot-password email flow.
- `activity_log` stores an audit trail of user registrations and profile updates.
- `offcuts` is a soft archive for suppliers removed during county audits.

The API layer lives in `app/main.py`, `app/auth_routes.py`, `app/request_routes.py`, and `app/admin_routes.py`. The SQL access layer lives in `app/db.py`.

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

## Required environment variables

For the web app:

```powershell
$env:SECRET_KEY        = "..."   # JWT signing key — set in production
$env:SMTP_USER         = "..."   # Gmail address for password reset emails
$env:SMTP_APP_PASSWORD = "..."   # Gmail app password (not your real password)
```

For the sourcing pipeline:

```powershell
$env:GOOGLE_PLACES_KEY = "..."
$env:ANTHROPIC_API_KEY = "..."
```

Without the pipeline keys, the web app can still run against an existing local database, but the sourcing pipeline cannot fetch or enrich new suppliers.

## User accounts

Create the first admin account:

```bash
python scripts/create_admin.py
```

Reset any user's password directly:

```bash
python scripts/reset_password.py
```

Designers register through the app UI. Admins can approve or reject their supplier add/edit requests from the Account tab.

## Deployment (Railway)

The app is hosted on [Railway](https://railway.app). The `Procfile` in the project root tells Railway how to run it:

```text
release: alembic upgrade head
web: uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
```

- `web` — starts the app and serves web traffic.
- `release` — runs automatically before each deploy. It applies any new Alembic migrations to the production database, so the schema is always up to date when new code goes live. This only changes database structure (tables, columns, constraints) — it never touches your data.

### Environment variables

Set these in Railway under your service → **Variables**:

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | PostgreSQL connection string — Railway sets this automatically when you add a Postgres database to your project |
| `SECRET_KEY` | Signs JWT auth tokens. Must be a long random string. Generate one with `python -c "import secrets; print(secrets.token_hex(32))"` |
| `SECURE_COOKIES` | Set to `true` in production so auth cookies are HTTPS-only |
| `SMTP_USER` | Gmail address used to send password reset emails |
| `SMTP_APP_PASSWORD` | Gmail app password (not your real Gmail password — generate one in Google Account → Security → App passwords) |

`DATABASE_URL` is the most critical one. Railway injects it automatically when you link a Postgres database to your service — you don't need to set it manually.

`SECRET_KEY` is used to sign JWT tokens (the cookies that keep users logged in). If it is not set, the app falls back to a hardcoded default that is public in the source code, which would allow anyone to forge login tokens. Always set a real value in production.

### What is a JWT token?

When a user logs in, the server creates a small JSON object with their ID and role, signs it with `SECRET_KEY`, and stores it as a cookie in their browser. On every subsequent request, the browser sends that cookie back automatically. The server verifies the signature to confirm the token is genuine and reads the user's identity from it — without needing a database lookup on every request. The signature is what makes tampering detectable: if anyone changes the payload (e.g. to elevate their role to admin), the signature no longer matches and the server rejects it.

### First deploy checklist

These steps only need to be done once when setting up a fresh production environment.

#### 1. Add a Postgres database in Railway

In your Railway project, add a new Postgres service. Railway will automatically set `DATABASE_URL` on your app service. The `release` step in the Procfile will create all the tables on first deploy.

#### 2. Migrate supplier data from local SQLite to production

Your local SQLite database (`database/traderoot.db`) holds all the curated supplier data. The production PostgreSQL database starts empty. Run this to copy the data across:

```bash
railway run python scripts/migrate_live_data.py
```

This reads from your local SQLite and writes into the production database via `DATABASE_URL`.

#### 3. Create the admin account in production

The `users` table starts empty in production. Running `create_admin.py` locally only creates an account in your local SQLite — it never reaches the live database. To create the admin account in production:

```bash
railway run python scripts/create_admin.py
```

The `railway run` prefix executes the script with your production environment variables, so it writes to the live database.

#### 4. Set the required environment variables

In Railway → your service → Variables, set at minimum:

- `SECRET_KEY` — a long random string
- `SECURE_COOKIES` — `true`
- `SMTP_USER` and `SMTP_APP_PASSWORD` — only needed if you want password reset emails to work

### Subsequent deploys

Push to your linked git branch and Railway deploys automatically. The `release` step runs `alembic upgrade head` before the new code goes live, so any new migrations are applied first. No manual steps needed.

### Running one-off scripts against production

Prefix any script with `railway run` to execute it with production environment variables:

```bash
railway run python scripts/reset_password.py
railway run python scripts/migrate_live_data.py
```

## Current data notes

- Surrey: 93 suppliers
- West Sussex: 95 suppliers
- East Sussex: imported
- Kent: imported
- Bedfordshire: imported
- Border suppliers can belong to multiple counties
- `primary_area_id` reflects the supplier's actual county location, not just the search county that found it

## Important design choices

- County imports are clean replaces, not additive merges, when a county is supplied to `04_import.py`.
- SQLite backups are written to `database/backups/` before each import only when the live DB is a local SQLite file.
- Audit scripts move removed suppliers into `offcuts` instead of hard-deleting them.
- Border tagging recalculates `primary_area_id` using the nearest configured county centre.
- All frontend filtering is client-side after `/api/map` loads the supplier set.
