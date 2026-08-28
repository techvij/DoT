import sys

import click
import yaml

from dot.connectors.postgres import PostgresConnector
from dot.results.store import ResultsStore
from dot.runner import CheckRunner

# Fall back to ASCII symbols on consoles that can't render Unicode
_USE_UNICODE = (sys.stdout.encoding or "").lower().replace("-", "") in ("utf8", "utf-8")
_ICONS = {
    "pass": "✓" if _USE_UNICODE else "OK  ",
    "warn": "⚠" if _USE_UNICODE else "WARN",
    "fail": "✗" if _USE_UNICODE else "FAIL",
}
_SEVERITY = {
    "low": "[LOW]",
    "medium": "[MEDIUM]",
    "high": "[HIGH]",
    "critical": "[CRITICAL]",
}


def _print_result(result, config_path: str) -> None:
    icon = _ICONS[result.status]
    label = f"{result.table}.{result.column}" if result.column else result.table
    severity_tag = _SEVERITY.get(result.severity, "") if result.status != "pass" else ""

    line = (
        f"{icon}  {label.ljust(26)}{result.check_name.ljust(15)}{result.status.ljust(7)}"
        f"({result.message})"
    )
    if severity_tag:
        line += f"  {severity_tag}"

    print(line)

    if result.check_name == "schema_drift" and result.status == "fail":
        print(
            f"   → To accept this change as the new baseline, run:\n"
            f"     python -m dot snapshot accept --table {result.table} --config {config_path}"
        )


@click.group()
def cli() -> None:
    pass


@cli.command()
@click.option("--config", default="config/checks.yaml", show_default=True, help="Path to checks YAML config")
@click.option("--table", default=None, help="Limit run to checks for this table only")
@click.option("--db", default="dot_results.db", show_default=True, help="Path to SQLite results DB")
def run(config: str, table: str | None, db: str) -> None:
    """Run all configured checks and print results."""
    store = ResultsStore(db)
    runner = CheckRunner(config, store)
    results = runner.run(table_filter=table)

    for result in results:
        _print_result(result, config)

    passed = sum(1 for r in results if r.status == "pass")
    warned = sum(1 for r in results if r.status == "warn")
    failed = sum(1 for r in results if r.status == "fail")

    print()
    print(f"{len(results)} checks run — {passed} passed, {warned} warned, {failed} failed")


@cli.group()
def snapshot() -> None:
    """Manage schema snapshots for drift detection."""
    pass


@snapshot.command("accept")
@click.option("--table", required=True, help="Table whose schema drift to accept as new baseline")
@click.option("--config", default="config/checks.yaml", show_default=True, help="Path to checks YAML config")
@click.option("--db", default="dot_results.db", show_default=True, help="Path to SQLite results DB")
def snapshot_accept(table: str, config: str, db: str) -> None:
    """Accept the current schema of TABLE as the new baseline (clears schema drift failure)."""
    with open(config) as f:
        cfg = yaml.safe_load(f)

    conn_cfg = cfg["connections"]["default"]
    connector = PostgresConnector(env_file=conn_cfg.get("env", ".env"))
    connector.connect()

    df = connector.run_query(
        f"SELECT column_name, data_type FROM information_schema.columns "
        f"WHERE table_name = '{table}' ORDER BY ordinal_position"
    )
    current = {row["column_name"]: row["data_type"] for _, row in df.iterrows()}

    store = ResultsStore(db)
    store.save_snapshot(table, current)
    print(
        f"Snapshot updated for '{table}' ({len(current)} columns). "
        f"schema_drift will pass on the next run."
    )


if __name__ == "__main__":
    cli()
