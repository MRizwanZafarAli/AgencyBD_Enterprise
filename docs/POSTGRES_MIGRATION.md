# PostgreSQL migration plan (not yet executed)

**Status:** designed, not implemented. This machine had no Docker daemon or Postgres, and a database rewrite must not ship untested. SQLite with
application-level tenant scoping is the current, tested model.

## When to migrate
Several API replicas, a managed database requirement, or tenant isolation enforced by the database itself (row-level security).

## Steps
1. **Driver layer.** `database/db.py::get_db()` is the only connection entry point. Add a Postgres implementation (psycopg 3, connection pool) behind the same context manager and a `DATABASE_URL` switch; keep SQLite for tests.
2. **SQL dialect.** All SQL is raw. Known differences to port: `?` placeholders to `%s`; `INSERT ... ON CONFLICT` (already portable); `strftime`/`datetime('now', ...)` to `now() - interval`; `AUTOINCREMENT` to `GENERATED ... AS IDENTITY`; `PRAGMA` calls removed; boolean columns as `boolean`.
3. **Schema.** Generate from `init_db()`; add `org_id` indexes already present; convert JSON text columns to `jsonb` where queried.
4. **Row-level security.** For every tenant table: `ALTER TABLE t ENABLE ROW LEVEL SECURITY; CREATE POLICY tenant ON t USING (org_id = current_setting('app.org_id'));` and `SET LOCAL app.org_id` at the start of each request transaction from the authenticated principal. Super-admin cross-tenant reads use a separate role.
5. **Data move.** Export with `sqlite3 .dump` per table, load with `COPY`; verify row counts and a checksum per table; run the full suite plus `scripts/e2e.sh` against Postgres in CI (service container).
6. **Cut-over.** Stop the app, final backup (`scripts/backup_db.py`), migrate, run smoke tests, start. Keep the SQLite file for rollback for 30 days.

## Acceptance
Full test suite green on Postgres; a cross-tenant read attempt through raw SQL with the wrong `app.org_id` returns zero rows; restore drill rehearsed.
