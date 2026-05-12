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

Auth, designer profiles, supplier requests, forgot-password flow, and all pending UX fixes
are implemented and committed. The app is fully functional locally against SQLite.

New files added since last baseline:

- `app/auth.py` — password hashing, JWT, Gmail SMTP reset email
- `app/auth_routes.py` — register, login, logout, me, forgot/reset password
- `app/request_routes.py` — designer supplier requests, admin review/approval
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

### Pending fixes / backlog

1. **Map search results list** — after approving a request, search results list now refreshes via `refreshSuppliers()`. ✓ Done.

2. **Supplier trade badge in detail modal** — was always showing Non-trade due to missing `s.trade` in `get_supplier_by_id` query. ✓ Fixed.

3. **UK postcode validation** — frontend regex validation on both add and request-add forms. ✓ Done.

4. **Category selection in request-add form** — categories fetched and rendered as checkboxes; `category_ids` included in payload. ✓ Done.

5. **Approved add requests now apply trade + categories** — `request_routes.py` approval path passes `trade` to `add_supplier` and calls `set_supplier_categories`. ✓ Done.

6. **Map initial zoom** — auto-zooms to fit all supplier data on first load. ✓ Done.

7. **County hover label** — stripped "Hover: " prefix. ✓ Done.

### Open backlog (to implement)

- Add more fixes here as they come up.
