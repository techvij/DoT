# Contributing to DoT

Thanks for your interest. DoT is a small, focused tool — contributions that keep it that way are most welcome.

## Ways to contribute

- **Bug reports** — open an issue describing what you ran, what you expected, and what happened. Include your connector type (Postgres / BigQuery) and Python version.
- **New checks** — open an issue first to describe what the check detects and why it can't be covered by an existing check. If it looks good, submit a PR.
- **New connectors** — same: issue first, then PR. A connector needs `connect()`, `run_query()`, and dialect overrides for `cast_float`, `cast_string`, `regex_match`, `resolve_table`, and `schema_query` where your database differs from Postgres.
- **Bug fixes** — PRs welcome, no issue needed for small fixes.

## How to submit a PR

```bash
# 1. Fork the repo on GitHub, then clone your fork
git clone https://github.com/<your-username>/DoT.git
cd DoT

# 2. Create a branch
git checkout -b my-feature

# 3. Install dev dependencies
pip install -r requirements-dev.txt

# 4. Make your changes

# 5. Run the tests — all must pass
pytest tests/ -v

# 6. Push and open a PR against main
git push origin my-feature
```

Open the PR from your fork's branch to `techvij/DoT:main`. Describe what the change does and why.

## Adding a new check

1. Create `dot/checks/your_check.py` — subclass `Check`, implement `run() -> CheckResult`
2. Register it in `CHECK_REGISTRY` in `dot/runner.py`
3. Add a commented example to `config/checks.yaml`
4. Add a section to `README.md` under **Checks**
5. Add at least one test in `tests/` (no database required — mock the connector)

See `dot/checks/cardinality.py` for a minimal example.

## Adding a new connector

1. Create `dot/connectors/your_connector.py` — subclass `BaseConnector`, implement `connect()` and `run_query()`
2. Override dialect methods where your SQL differs from Postgres defaults
3. Wire it in the `_build_connector_from_cfg()` helper in `dot/__main__.py` and `dot/runner.py`
4. Add a connection example to `config/checks.yaml` and `README.md`

## Code style

- No external formatter required — just keep it readable
- No comments that describe what the code does — only comments that explain *why* (non-obvious constraints, workarounds)
- New checks should handle `None` / empty DataFrame returns gracefully
- SQL must use connector dialect methods (`cast_float`, `cast_string`, `resolve_table`, `regex_match`) — never hardcode Postgres-specific syntax in a check
