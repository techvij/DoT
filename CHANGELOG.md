# Changelog

## v0.1.0 — 2026-08-29

First public release.

### Connectors
- **Postgres** — reads `POSTGRES_*` env vars via python-dotenv
- **BigQuery** — ADC (Cloud Shell / `gcloud auth application-default login`) or service account key; auto-detects 1-, 2-, and 3-part table names; backtick-quotes hyphenated project IDs; Cloud Shell identity fix (uses `gcloud auth print-access-token` instead of `google.auth.default()`)

### Checks (10 built-in)
| Check | Description |
|-------|-------------|
| `null_rate` | % nulls in a column exceeds threshold |
| `row_count` | Fixed minimum, run-over-run delta (`max_delta_pct`), or self-calibrating 7-day average |
| `freshness` | Most recent timestamp/date older than `max_age_hours`; handles TIMESTAMP, DATETIME, DATE, and string returns |
| `schema_drift` | Columns added, removed, or type-changed vs saved baseline |
| `duplicate` | Duplicate values — single column or composite grain (`columns: [a, b, c]`) |
| `value_range` | Numeric values outside configured min/max band |
| `allowed_values` | Values not in a defined set; optionally fail when expected values are absent (`require_all: true`) |
| `cardinality` | `COUNT(DISTINCT col)` outside `min_distinct` / `max_distinct` bounds |
| `custom_sql` | Bring-your-own SQL asserting result equals `expect`; `{table}` placeholder resolved with connector quoting |
| `regex` | Non-null values that don't match a pattern; `~` on Postgres, `REGEXP_CONTAINS` on BigQuery |

### Features
- SQLite results history (`dot_results.db`) — powers row count self-calibration and audit trail
- Schema drift accept workflow: `python -m dot snapshot accept --table <table>`
- Row count baseline reset: `python -m dot baseline reset --table <table>`
- Composite partition filters: `partition_column: year/month/date` / `partition_value: 2026/05/01`
- Per-run timestamped log files (`logs/dot_YYYYMMDD_HHMMSS.log`) — DEBUG to file, ERROR to console
- Per-check error isolation — one exception becomes `status=error`, run continues
- Cross-platform terminal output — Unicode icons with ASCII fallback
- Docker Compose demo with seeded Postgres data that intentionally triggers failures
