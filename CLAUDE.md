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

## Current state (2026-05-12)

Auth, designer profiles, supplier requests, forgot-password flow, geocoding, and all
pending UX fixes are implemented and committed. The app is fully functional locally
against SQLite.

New files added since last baseline:

- `app/auth.py` — password hashing, JWT, Gmail SMTP reset email
- `app/auth_routes.py` — register, login, logout, me, forgot/reset password
- `app/request_routes.py` — designer supplier requests, admin review/approval
- `app/geocode.py` — shared geocoding helpers (postcodes.io + Nominatim)
- `scripts/create_admin.py` — seed first admin account
- `scripts/reset_password.py` — CLI tool to reset any user's password directly

Migrations added:

- `a1b2c3d4e5f6` — users + supplier_requests tables
- `b2c3d4e5f6a7` — password_reset_tokens table
- `c3d4e5f6a7b8` — unique constraint on (supplier_id, designer_id) in reviews

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

### Open backlog

No known open items.
