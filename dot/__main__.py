import json
import sys

import click
import yaml

from dot.connectors.bigquery import BigQueryConnector
from dot.connectors.postgres import PostgresConnector
from dot.logger import setup_logger
from dot.results.store import ResultsStore
from dot.runner import CheckRunner

_USE_UNICODE = (sys.stdout.encoding or "").lower().replace("-", "") in ("utf8", "utf-8")
_ICONS = {
    "pass":  "✓" if _USE_UNICODE else "OK  ",
    "warn":  "⚠" if _USE_UNICODE else "WARN",
    "fail":  "✗" if _USE_UNICODE else "FAIL",
    "error": "!" if _USE_UNICODE else "ERR ",
}
_SEVERITY = {
    "low":      "[LOW]",
    "medium":   "[MEDIUM]",
    "high":     "[HIGH]",
    "critical": "[CRITICAL]",
}


def _result_to_dict(result) -> dict:
    return {
        "check_name":      result.check_name,
        "table":           result.table,
        "column":          result.column,
        "status":          result.status,
        "severity":        result.severity,
        "observed_value":  result.observed_value,
        "expected_value":  result.expected_value,
        "message":         result.message,
        "run_at":          result.run_at.isoformat(),
    }


def _print_result(result, config_path: str) -> None:
    icon = _ICONS.get(result.status, "?")
    label = f"{result.table}.{result.column}" if result.column else result.table
    severity_tag = _SEVERITY.get(result.severity, "") if result.status not in ("pass", "error") else ""

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

    if result.check_name == "row_count" and result.status in ("warn", "fail") and "7d avg" in result.message:
        print(
            f"   → If this drop is intentional (e.g. dropped partitions), reset the baseline:\n"
            f"     python -m dot baseline reset --table {result.table} --config {config_path}"
        )


def _build_connector_from_cfg(cfg: dict):
    conn_cfg = cfg["connections"]["default"]
    connector_type = conn_cfg["type"]
    if connector_type == "postgres":
        connector = PostgresConnector(env_file=conn_cfg.get("env", ".env"))
    elif connector_type == "bigquery":
        connector = BigQueryConnector(conn_cfg)
    else:
        raise ValueError(f"Unknown connector type: '{connector_type}'")
    connector.connect()
    return connector


@click.group()
def cli() -> None:
    pass


@cli.command()
@click.option("--config",   default="config/checks.yaml", show_default=True, help="Path to checks YAML config")
@click.option("--table",    default=None,                                     help="Limit run to checks for this table only")
@click.option("--db",       default="dot_results.db",     show_default=True, help="Path to SQLite results DB")
@click.option("--log-dir",  default="logs",               show_default=True, help="Directory for log files")
@click.option("--output",   default="text", type=click.Choice(["text", "json"], case_sensitive=False), show_default=True, help="Output format")
def run(config: str, table: str | None, db: str, log_dir: str, output: str) -> None:
    """Run all configured checks and print results."""
    logger, log_file = setup_logger(log_dir=log_dir)

    if output != "json":
        click.echo(f"Running DoT checks ({config})...")

    store = ResultsStore(db)
    runner = CheckRunner(config, store)
    results = runner.run(table_filter=table)

    if output == "json":
        print(json.dumps([_result_to_dict(r) for r in results], indent=2))
        return

    for result in results:
        _print_result(result, config)

    passed  = sum(1 for r in results if r.status == "pass")
    warned  = sum(1 for r in results if r.status == "warn")
    failed  = sum(1 for r in results if r.status == "fail")
    errored = sum(1 for r in results if r.status == "error")

    print()
    summary = f"{len(results)} checks run — {passed} passed, {warned} warned, {failed} failed"
    if errored:
        summary += f", {errored} errored"
    print(summary)
    print(f"Log: {log_file}")


@cli.group()
def snapshot() -> None:
    """Manage schema snapshots for drift detection."""
    pass


@snapshot.command("accept")
@click.option("--table",   required=True,                                     help="Table whose schema drift to accept as new baseline")
@click.option("--config",  default="config/checks.yaml", show_default=True, help="Path to checks YAML config")
@click.option("--db",      default="dot_results.db",     show_default=True, help="Path to SQLite results DB")
def snapshot_accept(table: str, config: str, db: str) -> None:
    """Accept the current schema of TABLE as the new baseline (clears schema drift failure)."""
    with open(config) as f:
        cfg = yaml.safe_load(f)

    connector = _build_connector_from_cfg(cfg)
    df = connector.run_query(connector.schema_query(table))
    current = {row["column_name"]: row["data_type"] for _, row in df.iterrows()}

    store = ResultsStore(db)
    store.save_snapshot(table, current)
    print(
        f"Snapshot updated for '{table}' ({len(current)} columns). "
        f"schema_drift will pass on the next run."
    )


@cli.group()
def baseline() -> None:
    """Manage row count baselines for self-calibrating checks."""
    pass


@baseline.command("reset")
@click.option("--table",  required=True,                                     help="Table whose row_count history to clear")
@click.option("--config", default="config/checks.yaml", show_default=True, help="Path to checks YAML config (unused, kept for consistency)")
@click.option("--db",     default="dot_results.db",     show_default=True, help="Path to SQLite results DB")
def baseline_reset(table: str, config: str, db: str) -> None:
    """Clear row_count history for TABLE so the next run starts a fresh baseline.

    Use this after an intentional change (e.g. dropping stale partitions) that
    permanently lowers the expected row count. The next run will pass and seed
    a new baseline from the current count.
    """
    store = ResultsStore(db)
    deleted = store.reset_row_count_baseline(table)
    print(
        f"Cleared {deleted} row_count history row(s) for '{table}'. "
        f"Next run will establish a new baseline from the current count."
    )


if __name__ == "__main__":
    cli()
