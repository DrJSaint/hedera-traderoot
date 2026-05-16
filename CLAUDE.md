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

## Current state (2026-05-15)

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

### UI polish pass (2026-05-15)

1. Tabs bolder — font-size 15px, font-weight 700, padding 13px 8px. ✓
2. Control panel (`map-toolbar`) background — `#a5d6a7` (Material green-300). ✓
3. Compact toolbar controls — 13px font, reduced padding; county dropdown text `var(--green)`. ✓
4. Search input — white background with inline SVG search icon; rounded rectangle (var(--radius)),
   max-width 190px matching postcode input. ✓
5. Ghost buttons — white background, `var(--green)` text, `var(--green-pale)` hover. ✓
6. Secondary action buttons (`#geolocate-btn`, `#postcode-clear`) — locked styles with
   explicit hover rules (ID-level to beat specificity). ✓
7. Geo-active button state — background matches toolbar (`#a5d6a7`) to ghost the button;
   `classList.add/remove('geo-active')` in `applyProximityCenter` / `clearProximityState`. ✓
8. Placeholder text standardised — `var(--text-muted)` with `opacity: 1` (Firefox fix). ✓
9. Radius slider label — "mi" → "miles". ✓
10. Marker click unified — single handler using `e.originalEvent?.pointerType === 'touch'`;
    desktop: single click opens detail; mobile: first tap shows tooltip, second tap opens
    detail. ✓
11. Status bar (`#map-status`) — white background. ✓
12. Results list (`.results-list`) — `#a5d6a7` background (matches toolbar). ✓
13. "Showing N of N" overflow text — colour `#1b2e22`. ✓
14. `.btn-ghost--dark` — explicit `background: transparent` added. ✓
15. Add Supplier + Account tabs — `background: #a5d6a7`; headings use `var(--text)` for
    contrast; `.tab-notice` text also darkened. ✓
16. Notification banners — white background (was pale green/pink, washed out on green tab). ✓
17. Past request cards — opacity restored to 1 (0.75 bled green through on coloured background). ✓
18. "No pending requests." text — `#1b2e22` (was `#888`, too faint on green). ✓

### Branding (2026-05-15)

App visible name changed from "Hedera TradeRoot" to "TradeRoot" — page title, logo alt
text, FastAPI title. Folder/repo name unchanged.

### Font picker

Admin-only — hidden by default, shown in `renderAuthUI()` only when `role === 'admin'`.
Default font: Outfit.

### Type filter pills

Active state: dot becomes `visibility: hidden` (holds space, no layout shift); label
shifted `left: -8px` via `position: relative` to re-centre text within the unchanged
pill width. Label wrapped in `<span class="pill-label">` in JS for CSS targeting.

### County borders

Checkbox removed (commented out in HTML + JS). Borders are always on. Re-enable by
uncommenting both blocks.

### Toolbar layout (map tab)

Three rows (desktop and mobile). County hover label hidden on mobile.

1. Search suppliers (max-width 190px) · County dropdown (fills remaining space)
2. Postcode input (max-width 190px) · [Search · My location · Clear] (`.postcode-btns` wrapper)
3. Type pills · Trade / Non-trade checkboxes

`.postcode-btns` uses `display: contents` on desktop (transparent to flex row) and
`display: flex` on mobile (groups buttons as one cell alongside the postcode input).
`#postcode-clear` lives inside `.postcode-btns` so it never overflows the row.

### Admin endpoints

- `GET /api/admin/requests` — all resolved supplier requests (admin only)
- `GET /api/admin/activity?event_type=` — activity log, filterable (admin only)

### Railway deployment (fixed 2026-05-14)

- Procfile `release:` phase is silently ignored by Railway (Heroku-only feature).
  Migrations now chained into the `web` command: `alembic upgrade head && uvicorn ...`
- `SECURE_COOKIES` env var added — set to `true` in Railway to enable Secure flag on auth cookies.
- Admin account created manually in production via Railway Postgres query editor (psycopg DLL blocked by Windows Application Control policy, so `railway run` scripts could not connect to PostgreSQL locally).
- Railway's query editor runs one SQL statement at a time — multi-statement blocks are silently truncated.

### UI session (2026-05-16)

1. Geo search hover fix — county/district hover label was broken in geo search mode because
   the radius circle (no `interactive: false`) sat on top of county boundary layers and ate
   all mouse events. Fixed by adding `interactive: false` to the `L.circle` options. ✓

2. Floating glass toolbar — `.map-toolbar` is now always `position: absolute` over the map
   (`top: 8px; left: 8px; width: fit-content; max-width: calc(100% - 16px); z-index: 500`).
   `#tab-map` has `position: relative`. Default visual: glass-gradient (green-tinted frosted
   glass). ✓

3. Toolbar style picker — admin-only dropdown in the header (next to font picker). Four options
   saved to `localStorage('traderoot-toolbar-style')`:
   - `""` — Glass Gradient (default, green-tinted frosted)
   - `"glass"` — Glass (plain white frosted)
   - `"green-gradient"` — solid gradient green
   - `"green"` — flat solid green
   Applied via `body[data-toolbar-style]` CSS attribute. ✓

4. Add Supplier / Account tab backgrounds — replaced flat `#a5d6a7` with
   `linear-gradient(160deg, #c8e6c9 0%, #80c883 100%)`. ✓

5. Form card glassmorphism — `.form-card` now uses `background: rgba(255,255,255,0.55)` +
   `backdrop-filter: blur(20px)` + `border-radius: 14px` to match the toolbar aesthetic. ✓

6. Geo-active button — `#geolocate-btn.geo-active` updated from `#a5d6a7` (matched old solid
   toolbar) to `rgba(45,106,79,0.15)` green tint, appropriate for glass context. ✓

### Open backlog

No known open items.
