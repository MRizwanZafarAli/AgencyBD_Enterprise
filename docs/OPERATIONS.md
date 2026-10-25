# Operations

## Releases (replaces the removed in-app updater)
`scripts/release.sh [version]` runs the full gate (backend tests, type-check, lint, build, secret scan, backup-restore drill, image build) and writes `RELEASE.json`.
It never pushes or deploys. Promote the image through your normal process: staging first, then production.

## Environments
| | development | staging | production |
|---|---|---|---|
| `AGENCYBD_ENV` | development | production (with a separate `.env`, database and sender domains) | production |
| Secrets | generated locally | its own set | its own set, from a secret manager |
Staging must use its own sending domains and mailboxes; never point staging at production prospects.

## Backups and restore
- Backup: `python scripts/backup_db.py --keep 14` (online SQLite backup, integrity-checked, rotated). The compose file runs it daily.
- Restore drill: `python scripts/restore_db.py data/backups/<file> --yes` with the API stopped; the previous database is kept next to it. A test proves backup → modify → restore → verify.
- Run the drill after every schema change and monthly.

## Monitoring
- `/metrics` (needs a key with `metrics:read`): request counts and latency by route template, discovery runs, re-scan alerts, background failures, per-tenant stop-sending switch, bounces and sends.
- Alert rules: `ops/prometheus_alerts.yml` (API down, 5xx rate, slow routes, background failures, bounce rate above 2%).
- Logs are JSON with a `trace_id` equal to the `X-Request-ID` header (send your own to correlate with a proxy).

## Runbook
- **Bounce alert:** press Stop sending, check the list source and verifier, resume only after fixing.
- **Scheduler failing:** `agencybd_background_failures_total{job="scheduler"}`; read the log lines with `event` and `trace_id`; the scheduler resumes automatically.
- **Leaked key:** revoke it in Settings > Team and keys, then rotate with `scripts/create_admin_key.py`.
- **Interrupted discovery run:** shown as failed after 15 minutes; just start a new one.
- **Database growth:** the vulnerability cache and discovery runs can be pruned safely (`vuln_cache`, `discovery_runs`).

## Capacity notes
SQLite (WAL) with one pooled connection per thread handled two racing scheduler workers and 300 concurrent audits in tests. Move to PostgreSQL (see `docs/POSTGRES_MIGRATION.md`) before running several API replicas.
