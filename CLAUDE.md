# Hedera TradeRoot — Agent Notes

Read `README.md` first. It is the canonical source of truth for architecture,
database setup, and pipeline workflow.

This file exists only for agent-specific reminders:

- Treat Alembic migrations as the live schema authority.
- Treat `database/pipeline.db` as a separate SQLite staging database.
- Use `DATABASE_URL` for the live database.
- Prefer validating migration-related changes against a temporary database first.
- Keep docs and setup files aligned with the actual runtime workflow.
