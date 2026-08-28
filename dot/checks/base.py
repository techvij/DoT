from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from dot.connectors.base import BaseConnector


@dataclass
class CheckResult:
    check_name: str
    table: str
    column: str | None
    status: Literal["pass", "warn", "fail", "error"]
    severity: Literal["low", "medium", "high", "critical"]
    observed_value: float | str | None
    expected_value: float | str | None
    message: str
    run_at: datetime


class Check(ABC):
    def __init__(self, connector: BaseConnector, config: dict):
        self.connector = connector
        self.config = config

    @abstractmethod
    def run(self) -> CheckResult: ...

    def _partition_clause(self) -> str:
        """
        Builds an AND-joined filter fragment from optional partition config.

        YAML shape:
          partition_column: year/month/date   # slash-separated column names
          partition_value:  2026/05/01        # slash-separated values (same order)

        All values are treated as strings. Returns "" when not configured.
        Example output: "year = '2026' AND month = '05' AND date = '01'"
        """
        cols_raw = self.config.get("partition_column", "")
        vals_raw = self.config.get("partition_value", "")
        if not cols_raw or not vals_raw:
            return ""
        cols = [c.strip() for c in str(cols_raw).split("/")]
        vals = [v.strip() for v in str(vals_raw).split("/")]
        if len(cols) != len(vals):
            raise ValueError(
                f"partition_column has {len(cols)} part(s) but partition_value has {len(vals)}"
            )
        return " AND ".join(f"{c} = '{v}'" for c, v in zip(cols, vals))

    def _where(self, extra: str = "") -> str:
        """Combines partition clause and any extra filter into a full WHERE block."""
        parts = [p for p in [self._partition_clause(), extra] if p]
        return f"WHERE {' AND '.join(parts)}" if parts else ""
