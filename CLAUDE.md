# Hedera TradeRoot — Agent Notes

Read `README.md` first. It is the canonical source of truth for architecture,
database setup, and pipeline workflow.

This file exists only for agent-specific reminders:

- Treat Alembic migrations as the live schema authority.
- Treat `database/pipeline.db` as a separate SQLite staging database.
- Use `DATABASE_URL` for the live database.
- Prefer validating migration-related changes against a temporary database first.
- Keep docs and setup files aligned with the actual runtime workflow.
- After writing any Alembic migration file, immediately run `alembic upgrade head` before moving on.

---

## Current state (2026-05-14)

Auth, designer profiles, supplier requests, forgot-password flow, geocoding, admin
activity log, and all UX fixes are implemented and committed. The app is fully
functional locally against SQLite.

New files added since last baseline:

- `app/auth.py` — password hashing, JWT, Gmail SMTP reset email
- `app/auth_routes.py` — register, login, logout, me, forgot/reset password
- `app/request_routes.py` — designer supplier requests, admin review/approval
- `app/geocode.py` — shared geocoding helpers (postcodes.io + Nominatim)
- `app/admin_routes.py` — admin-only endpoints: request history + activity log
- `scripts/create_admin.py` — seed first admin account
- `scripts/reset_password.py` — CLI tool to reset any user's password directly

Migrations added:

- `a1b2c3d4e5f6` — users + supplier_requests tables
- `b2c3d4e5f6a7` — password_reset_tokens table
- `c3d4e5f6a7b8` — unique constraint on (supplier_id, designer_id) in reviews
- `d4e5f6a7b8c9` — activity_log table

Environment variables required for full functionality:

- `DATABASE_URL` — live database (defaults to local SQLite)
- `SECRET_KEY` — JWT signing key
- `SMTP_USER` + `SMTP_APP_PASSWORD` — Gmail app password for reset emails

### Completed fixes

1. Map search results refresh via `refreshSuppliers()` after admin approve/reject. ✓
2. Supplier trade badge in detail modal — was missing `s.trade` in SELECT query. ✓
3. UK postcode regex validation on add and request-add forms. ✓
4. Category checkboxes in request-add form (fetched async, side-by-side flex layout). ✓
5. Approved add requests now geocode the address before calling `add_supplier()`. ✓
6. Approved add requests apply `trade` flag and `category_ids` on supplier creation. ✓
7. Map auto-zooms to fit all supplier pins on first load. ✓
8. County hover label no longer shows "Hover: " prefix. ✓
9. Admin geocoding failure warning — if `resolve_coordinates()` returns `(None, None)`,
   supplier is still created but response includes `geocode_failed: true`. Frontend shows
   a dismissible yellow banner with a link to open the supplier for editing. ✓
10. Map zoom no longer resets to UK-wide when clicking type pills, clearing search,
    selecting "All Counties", or clearing a postcode search — always fits to suppliers. ✓
11. Mobile two-tap markers — first tap shows tooltip (name/type/rating), second tap
    opens the detail modal. Desktop unchanged (hover tooltip, click opens modal). ✓
    Implementation: per-marker `_firstTap` flag + `L.DomEvent.stopPropagation` on
    click to prevent map-level handler undoing tap state in the same cycle.
12. Admin account tab has three sub-tabs: Pending (approve/reject queue), History
    (all resolved requests), Activity (registrations and profile updates). ✓
13. Activity log — registrations and profile updates are written to `activity_log`
    table and visible to admin under the Activity sub-tab, filterable by event type. ✓
14. Mobile toolbar overflow fixed — toolbar rows wrap on narrow screens; search input
    flexible width, postcode input flexible, county hover label hidden on mobile. ✓
15. Map initial centering fixed — `UK_BOUNDS` eastern limit extended from 2.5°E to
    10°E; `maxBoundsViscosity: 1.0` was dragging fitBounds center west to UK_CENTER
    on wide viewports. Also adds `invalidateSize()` + `requestAnimationFrame` before
    the initial `fitBounds` call. ✓
16. Redundant account header removed — name/email/logout block was duplicating the
    site header; removed from both admin and designer account views. ✓
17. SVG focus ring suppressed — `.leaflet-interactive:focus { outline: none }`. ✓

### Toolbar layout (map tab)

Three rows (desktop). On mobile (≤640px) the search input takes a full-width row,
county dropdown + borders toggle share the row below, hover label is hidden.

1. Search suppliers · County dropdown · County borders toggle · hover label
2. Postcode · Search · My location · Clear
3. Type pills · Trade / Non-trade checkboxes

### Admin endpoints

- `GET /api/admin/requests` — all resolved supplier requests (admin only)
- `GET /api/admin/activity?event_type=` — activity log, filterable (admin only)

### Railway deployment (fixed 2026-05-14)

- Procfile `release:` phase is silently ignored by Railway (Heroku-only feature).
  Migrations now chained into the `web` command: `alembic upgrade head && uvicorn ...`
- `SECURE_COOKIES` env var added — set to `true` in Railway to enable Secure flag on auth cookies.
- Admin account created manually in production via Railway Postgres query editor (psycopg DLL blocked by Windows Application Control policy, so `railway run` scripts could not connect to PostgreSQL locally).
- Railway's query editor runs one SQL statement at a time — multi-statement blocks are silently truncated.

### Open backlog

No known open items.
