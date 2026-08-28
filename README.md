# DoT — Data Observability Tool

DoT is not an ETL tool. It doesn't move data. It sits beside your ETL pipeline and watches what lands.

## Mental model

```
Source Systems          ETL Pipeline           Target / Warehouse
(APIs, DBs, files)  →  (Airflow, dbt, etc) →  (Postgres, BigQuery)
                                                        ↓
                                                      DoT
                                                (runs checks here,
                                                 on the data that
                                                 already landed)
```

DoT only ever connects to one place — wherever your data lives after it's been loaded. It doesn't touch source systems at all. It asks questions like:

- Did enough rows land in `orders` today?
- Are there nulls in columns that shouldn't have nulls?
- Is the data fresh, or did the pipeline silently fail?
- Did the schema change unexpectedly?

All of that is answerable by querying the target database directly. No ETL knowledge needed, no source system access needed.

---

## What it is

A lightweight CLI tool for small data teams and solo data engineers who need pipeline health monitoring without the complexity or cost of enterprise platforms. Define checks in YAML, run against Postgres (BigQuery coming), get results in your terminal. No platform, no login, no infrastructure beyond a SQLite file for history.

---

## Quick start

### With Docker (recommended — zero config)

```bash
docker compose up --build
```

This starts a Postgres instance seeded with realistic data that intentionally triggers several check failures, then runs all checks against it. You'll see a mix of pass/warn/fail on first run.

### Local

```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your Postgres credentials
python -m dot run --config config/checks.yaml
```

---

## Terminal output

```
✗  orders.status          null_rate      fail   (5.6% null (threshold: 1.0%))  [HIGH]
✗  orders                 row_count      fail   (800 rows (minimum: 1,000))    [HIGH]
✗  events.created_at      freshness      fail   (last record 20.3h ago, threshold 6h)  [CRITICAL]
✗  orders.order_id        duplicate      fail   (40 duplicate values in order_id (40 extra rows))  [HIGH]
✗  payments.amount        value_range    fail   (min -50.0 < 0)  [HIGH]
✓  orders                 schema_drift   pass   (Snapshot saved (baseline established))

6 checks run — 1 passed, 0 warned, 5 failed
```

---

## CLI reference

```bash
# Run all checks
python -m dot run --config config/checks.yaml

# Run checks for one table only
python -m dot run --config config/checks.yaml --table orders

# Accept a schema change as the new baseline
python -m dot snapshot accept --table orders --config config/checks.yaml
```

---

## YAML config

```yaml
connections:
  default:
    type: postgres
    env: .env          # path to your .env file

checks:
  - table: orders
    column: status
    check: null_rate
    threshold: 0.01    # fail if > 1% null
    severity: high

  - table: orders
    check: row_count
    min_rows: 1000     # omit to use self-calibrating 7-day rolling average
    severity: high

  - table: events
    column: created_at
    check: freshness
    max_age_hours: 6
    severity: critical

  - table: orders
    column: order_id
    check: duplicate
    severity: high

  - table: payments
    column: amount
    check: value_range
    min: 0
    max: 1000000
    severity: high

  - table: orders
    check: schema_drift
    severity: medium
```

### Partition filters (multi-column)

Any check (except `schema_drift`) supports partition filtering. Useful for BigQuery-style partitioned tables where you want to scope the check to a specific date partition:

```yaml
- table: events_partitioned
  column: created_at
  check: freshness
  max_age_hours: 6
  severity: high
  partition_column: year/month/date   # slash-separated column names
  partition_value: 2026/05/01         # slash-separated values (same order)
```

This generates `WHERE year = '2026' AND month = '05' AND date = '01'`. All values are treated as strings. Multiple columns are `AND`-ed together.

---

## Checks

| Check | What it detects |
|-------|----------------|
| `null_rate` | % of nulls in a column exceeds a threshold |
| `row_count` | Table has too few rows (vs fixed minimum or self-calibrating 7-day average) |
| `freshness` | Most recent timestamp is older than `max_age_hours` |
| `schema_drift` | Columns added, removed, or type-changed vs saved baseline |
| `duplicate` | Duplicate values on a column or composite key that should be unique |
| `value_range` | Numeric column values outside a configured min/max band |
| `allowed_values` | Column contains values not in a defined allowed set (NULLs excluded — use `null_rate` for those) |

---

## Schema drift

On first run, `schema_drift` saves a baseline snapshot and passes. On subsequent runs it diffs the current schema against the snapshot. If it fails, DoT tells you exactly what changed and how to accept it:

```
✗  orders   schema_drift   fail   (column 'phone' added)  [MEDIUM]
   → To accept this change as the new baseline, run:
     python -m dot snapshot accept --table orders --config config/checks.yaml
```

Run the accept command when a schema change is intentional. The baseline stays fixed until you explicitly accept it — this forces a deliberate acknowledgment rather than silently swallowing changes.

---

## Results history

Every run is persisted to a SQLite file (`dot_results.db` by default). This powers self-calibrating row count checks: if you omit `min_rows`, DoT computes a 7-day rolling average from history and warns when the current count drops below 80% of that average.

---

## Adding a new connector

Create a new file in `dot/connectors/` that subclasses `BaseConnector` and implements `connect()` and `run_query()`. No changes needed anywhere else.

## Adding a new check

Create a new file in `dot/checks/` that subclasses `Check` and implements `run() -> CheckResult`. Register it in `CHECK_REGISTRY` in `dot/runner.py`. Done.

---

## What's next (Phase 2)

- BigQuery connector
- Claude AI integration for natural-language failure summaries
- Slack / email alerting
