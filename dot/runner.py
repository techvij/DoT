import logging
import uuid
from datetime import datetime, timezone

import yaml

from dot.checks.allowed_values import AllowedValuesCheck
from dot.checks.base import CheckResult
from dot.checks.duplicate import DuplicateCheck
from dot.checks.freshness import FreshnessCheck
from dot.checks.null_rate import NullRateCheck
from dot.checks.row_count import RowCountCheck
from dot.checks.schema_drift import SchemaDriftCheck
from dot.checks.value_range import ValueRangeCheck
from dot.connectors.bigquery import BigQueryConnector
from dot.connectors.postgres import PostgresConnector
from dot.results.store import ResultsStore

logger = logging.getLogger("dot")

CHECK_REGISTRY = {
    "null_rate": NullRateCheck,
    "row_count": RowCountCheck,
    "freshness": FreshnessCheck,
    "schema_drift": SchemaDriftCheck,
    "duplicate": DuplicateCheck,
    "value_range": ValueRangeCheck,
    "allowed_values": AllowedValuesCheck,
}

_STORE_AWARE = {"row_count", "schema_drift"}


class CheckRunner:
    def __init__(self, config_path: str, store: ResultsStore):
        self.config_path = config_path
        self.store = store
        with open(config_path) as f:
            self.config = yaml.safe_load(f)

    def _build_connector(self):
        conn_cfg = self.config["connections"]["default"]
        connector_type = conn_cfg["type"]
        if connector_type == "postgres":
            connector = PostgresConnector(env_file=conn_cfg.get("env", ".env"))
        elif connector_type == "bigquery":
            connector = BigQueryConnector(conn_cfg)
        else:
            raise ValueError(f"Unknown connector type: '{connector_type}'")
        connector.connect()
        return connector

    def run(self, table_filter: str | None = None) -> list[CheckResult]:
        run_id = str(uuid.uuid4())
        logger.info(f"Run started — run_id: {run_id}, config: {self.config_path}")

        connector = self._build_connector()
        checks_config = self.config.get("checks", [])

        if table_filter:
            checks_config = [c for c in checks_config if c.get("table") == table_filter]
            logger.info(f"Table filter active: {table_filter} ({len(checks_config)} checks)")

        results = []

        for check_conf in checks_config:
            check_name = check_conf.get("check")
            table = check_conf.get("table")
            column = check_conf.get("column")
            label = f"{table}.{column}" if column else table

            cls = CHECK_REGISTRY.get(check_name)
            if cls is None:
                logger.warning(f"Unknown check type '{check_name}' — skipping")
                continue

            logger.info(f"Running {check_name} on {label}")
            try:
                if check_name in _STORE_AWARE:
                    check = cls(connector, check_conf, store=self.store)
                else:
                    check = cls(connector, check_conf)

                result = check.run()
                logger.info(f"[{label}] {check_name} → {result.status} ({result.message})")

            except Exception as exc:
                logger.error(
                    f"[{label}] {check_name} → EXCEPTION: {exc}",
                    exc_info=True,
                )
                result = CheckResult(
                    check_name=check_name,
                    table=table,
                    column=column,
                    status="error",
                    severity=check_conf.get("severity", "medium"),
                    observed_value=None,
                    expected_value=None,
                    message=f"{type(exc).__name__}: {exc}",
                    run_at=datetime.now(timezone.utc),
                )

            results.append(result)

        self.store.save(results, run_id)

        passed  = sum(1 for r in results if r.status == "pass")
        warned  = sum(1 for r in results if r.status == "warn")
        failed  = sum(1 for r in results if r.status == "fail")
        errored = sum(1 for r in results if r.status == "error")
        logger.info(
            f"Run complete — {len(results)} checks: "
            f"{passed} passed, {warned} warned, {failed} failed, {errored} errored"
        )

        return results
