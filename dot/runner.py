import uuid

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

CHECK_REGISTRY = {
    "null_rate": NullRateCheck,
    "row_count": RowCountCheck,
    "freshness": FreshnessCheck,
    "schema_drift": SchemaDriftCheck,
    "duplicate": DuplicateCheck,
    "value_range": ValueRangeCheck,
    "allowed_values": AllowedValuesCheck,
}

CONNECTOR_REGISTRY = {
    "postgres": PostgresConnector,
    "bigquery": BigQueryConnector,
}

# Checks that receive the results store so they can read/write history or snapshots
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
        cls = CONNECTOR_REGISTRY[connector_type]
        if connector_type == "postgres":
            env_file = conn_cfg.get("env", ".env")
            connector = cls(env_file=env_file)
        else:
            connector = cls()
        connector.connect()
        return connector

    def run(self, table_filter: str | None = None) -> list[CheckResult]:
        connector = self._build_connector()
        checks_config = self.config.get("checks", [])

        if table_filter:
            checks_config = [c for c in checks_config if c.get("table") == table_filter]

        run_id = str(uuid.uuid4())
        results = []

        for check_conf in checks_config:
            check_name = check_conf.get("check")
            cls = CHECK_REGISTRY.get(check_name)
            if cls is None:
                continue

            if check_name in _STORE_AWARE:
                check = cls(connector, check_conf, store=self.store)
            else:
                check = cls(connector, check_conf)

            result = check.run()
            results.append(result)

        self.store.save(results, run_id)
        return results
