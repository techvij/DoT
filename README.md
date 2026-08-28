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
- Are there values in `status` that aren't in the approved set?

All of that is answerable by querying the target database directly. No ETL knowledge needed, no source system access needed.

---

## What it is

A lightweight CLI tool for small data teams and solo data engineers who need pipeline health monitoring without the complexity or cost of enterprise platforms. Define checks in YAML, run against Postgres or BigQuery, get results in your terminal. No platform, no login, no infrastructure beyond a SQLite file for history.

---

## Quick start

### With Docker (recommended — zero config)

```bash
docker compose up --build
```

Starts a Postgres instance seeded with realistic data that intentionally triggers several check failures, then runs all checks against it. You'll see a mix of pass/warn/fail on first run.

### Local — Postgres

```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your Postgres credentials
python -m dot run --config config/checks.yaml
```

### Local — BigQuery

```bash
pip install -r requirements.txt
gcloud auth application-default login   # once; not needed in Cloud Shell
# Edit config/checks.yaml — see BigQuery section below
python -m dot run --config config/checks.yaml
```

### Cloud Shell

Cloud Shell's Python is OS-managed (PEP 668), so `pip install` requires the `--break-system-packages` flag:

```bash
git clone https://github.com/techvij/DoT.git && cd DoT
pip install -r requirements.txt --break-system-packages
# No auth needed — Cloud Shell detects GOOGLE_CLOUD_SHELL=true automatically
# Edit config/checks.yaml with your project/dataset/tables
python -m dot run --config config/checks.yaml
```

---

## Terminal output

```
✗  orders.status          null_rate      fail   (5.6% null (threshold: 1.0%))             [HIGH]
✗  orders                 row_count      fail   (800 rows (minimum: 1,000))               [HIGH]
✗  events.created_at      freshness      fail   (last record 20.3h ago, threshold 6h)    [CRITICAL]
✗  orders.order_id        duplicate      fail   (40 duplicate values (40 extra rows))     [HIGH]
✗  payments.amount        value_range    fail   (min -50.0 < 0)                           [HIGH]
✓  orders                 schema_drift   pass   (Snapshot saved (baseline established))
!  orders.status          allowed_values error  (OperationalError: connection closed)

7 checks run — 1 passed, 0 warned, 5 failed, 1 errored
Log: logs/dot_20260828_143022.log
```

Icons: `✓` pass · `⚠` warn · `✗` fail · `!` error (exception — full traceback in log file).
Falls back to `OK` / `WARN` / `FAIL` / `ERR` on terminals that don't support Unicode.

---

## CLI reference

```bash
# Run all checks
python -m dot run --config config/checks.yaml

# Run checks for one table only
python -m dot run --config config/checks.yaml --table orders

# Custom log directory
python -m dot run --config config/checks.yaml --log-dir /var/log/dot

# Accept a schema change as the new baseline
python -m dot snapshot accept --table orders --config config/checks.yaml

# Reset row_count baseline after an intentional data change (e.g. dropped partitions)
python -m dot baseline reset --table orders --config config/checks.yaml
```

---

## YAML config

### Postgres

```yaml
connections:
  default:
    type: postgres
    env: .env          # path to .env file with POSTGRES_* vars
```

### BigQuery

```yaml
connections:
  default:
    type: bigquery
    project: my-gcp-project-id
    dataset: my_dataset          # default dataset for unqualified table names
    # credentials_file: /path/to/sa_key.json   # omit to use ADC (gcloud / Cloud Shell)
```

**Table naming** — three formats supported, auto-detected by dot count:

| In checks.yaml | Resolved as |
|----------------|-------------|
| `orders` | `project.dataset.orders` (uses config defaults) |
| `my_dataset.orders` | `project.my_dataset.orders` (uses config project) |
| `my-project.my_dataset.orders` | fully self-contained |

BigQuery project IDs that contain hyphens are automatically backtick-quoted in SQL.

---

## Checks

| Check | What it detects | Key config |
|-------|----------------|------------|
| `null_rate` | % of nulls in a column exceeds a threshold | `threshold: 0.01` |
| `row_count` | Too few rows vs fixed minimum or self-calibrating 7-day average | `min_rows: 1000` (omit to self-calibrate) |
| `freshness` | Most recent timestamp is older than `max_age_hours` | `max_age_hours: 6` |
| `schema_drift` | Columns added, removed, or type-changed vs saved baseline | — |
| `duplicate` | Duplicate values on a column that should be unique | `column: order_id` |
| `value_range` | Numeric column values outside a configured min/max band | `min: 0`, `max: 1000000` |
| `allowed_values` | Column contains values not in a defined set, or expected values are absent | `values: a,b,c`, `require_all: true` |

### allowed_values — two directions

`allowed_values` checks in both directions when `require_all: true`:

```yaml
- table: orders
  column: status
  check: allowed_values
  values: completed,pending,cancelled,refunded
  require_all: true       # also fail if any listed value never appears in the column
  severity: high
```

| Scenario | `require_all: false` (default) | `require_all: true` |
|----------|-------------------------------|---------------------|
| Column has `A,B,C`, list is `A,B,C` | pass | pass |
| Column has `A,B,D`, list is `A,B,C` | fail — `D` is unexpected | fail — `D` unexpected + `C` absent |
| Column has `A,B`, list is `A,B,C` | pass | fail — `C` absent |

NULLs are always excluded from both directions — use `null_rate` to check for those separately.

### Partition filters (multi-column)

Any check except `schema_drift` supports partition filtering. Useful for BigQuery partitioned tables:

```yaml
- table: events_partitioned
  column: created_at
  check: freshness
  max_age_hours: 6
  severity: high
  partition_column: year/month/date   # slash-separated column names
  partition_value: 2026/05/01         # slash-separated values (same order)
```

Generates `WHERE year = '2026' AND month = '05' AND date = '01'`. Multiple columns are `AND`-ed together. All values are treated as strings.

---

## Schema drift

On first run, `schema_drift` saves a baseline snapshot and passes. On subsequent runs it diffs the current schema against the snapshot. If it fails, DoT tells you exactly what changed and how to accept it:

```
✗  orders   schema_drift   fail   (column 'phone' added)  [MEDIUM]
   → To accept this change as the new baseline, run:
     python -m dot snapshot accept --table orders --config config/checks.yaml
```

Run the accept command when a schema change is intentional. The baseline stays fixed until you explicitly accept it.

---

## BigQuery auth

DoT supports two auth methods for BigQuery:

**Application Default Credentials (ADC)** — recommended. Works automatically in Cloud Shell, or run once locally:

```bash
gcloud auth application-default login
```

No config needed in DoT — the client picks it up automatically.

**Service account key** — for CI/CD or machines without `gcloud`:

```yaml
connections:
  default:
    type: bigquery
    project: my-project
    dataset: my_dataset
    credentials_file: /path/to/sa_key.json
```

---

## Logging

Every run writes a timestamped log file to `logs/` (or `--log-dir` of your choice):

```
logs/dot_20260828_143022.log
```

**What's in the log:**
- Run start with `run_id` (ties back to SQLite history)
- Connector connection details
- Every check: start, result, message
- Full exception tracebacks for any errored checks (terminal shows only a one-liner)

The log path is printed at the end of every terminal run. One failed check never crashes the rest — it becomes `status=error` and the run continues.

---

## Results history

Every run is persisted to SQLite (`dot_results.db` by default). This powers:
- **Self-calibrating row count**: omit `min_rows` and DoT uses a 7-day rolling average from history — warns when current count drops below 80% of that average
- **Audit trail**: query `dot_results.db` directly to see all historical check outcomes per table

---

## Adding a new connector

Create a new file in `dot/connectors/` subclassing `BaseConnector`. Implement `connect()` and `run_query()`. Override `cast_float()`, `cast_string()`, `schema_query()`, and `resolve_table()` if the connector has a different SQL dialect or table-naming convention. No changes needed anywhere else.

## Adding a new check

Create a new file in `dot/checks/` subclassing `Check` and implementing `run() -> CheckResult`. Register it in `CHECK_REGISTRY` in `dot/runner.py`. Done.

---

## What's next (Phase 2)

- Claude AI integration for natural-language failure summaries
- Slack / email alerting
- `check: custom_sql` — run any SQL and assert on the result
