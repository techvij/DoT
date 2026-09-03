# Changelog

## v0.3.0 — 2026-09-03

### Added
- **Claude API integration** — AI-generated plain-English diagnostic summary after each run (`claude-sonnet-4-6`, single API call per run, JSON-structured output with `overall_status`, per-finding `plain_english` / `likely_cause` / `investigate_first`, and `next_run_action`)
- **Slack alerting** — Block Kit formatted webhook messages; Claude diagnosis embedded per finding; configurable `notify_on: always | warn_fail | fail_only`
- **`dot/report/` layer** — `formatter.py` (shared utilities), `claude_summary.py`, `slack_alert.py`
- **`--no-claude` and `--no-slack` CLI flags** — skip report integrations for local dev runs without firing alerts
- **`ANTHROPIC_API_KEY` and `SLACK_WEBHOOK_URL`** added to `.env.example`; both fully optional — DoT runs identically if neither is set
- **13 new tests** in `tests/test_report.py` — all mock-based, no real API calls or network

### Changed
- `requirements.txt` — added `requests>=2.31.0,<3` and `anthropic>=0.34.0,<1`

---

## v0.2.0 — 2026-08-31

### Added
- **GitHub Actions CI** — pytest runs automatically on every push and every PR to `main` (Python 3.11, ubuntu-latest)
- **`--output json` flag** — `python -m dot run --output json` emits a JSON array of all check results; pipe-friendly for `jq` or downstream tooling
- **56 mock-connector tests** — all 10 check types covered with no database or cloud credentials required (`tests/test_checks.py`)
- **CONTRIBUTING.md** — fork/PR workflow, steps for adding a new check or connector, code style guide

### Fixed
- Suppressed repetitive pandas SQLAlchemy compatibility warning in Postgres connector
- Removed project-specific example table/column names; replaced with generic e-commerce equivalents
- Docker demo thresholds tuned so the first run shows a realistic mix of pass/warn/fail

---

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
