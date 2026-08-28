from datetime import datetime, timezone

from dot.checks.base import Check, CheckResult


class ValueRangeCheck(Check):
    def run(self) -> CheckResult:
        table = self.config["table"]
        column = self.config["column"]
        min_val = self.config.get("min")
        max_val = self.config.get("max")
        severity = self.config.get("severity", "medium")
        where = self._where()

        sql = f"SELECT MIN({column}) AS min_val, MAX({column}) AS max_val FROM {table} {where}"
        df = self.connector.run_query(sql)
        observed_min = df["min_val"].iloc[0]
        observed_max = df["max_val"].iloc[0]

        violations = []
        if min_val is not None and observed_min is not None and float(observed_min) < float(min_val):
            violations.append(f"min {observed_min} < {min_val}")
        if max_val is not None and observed_max is not None and float(observed_max) > float(max_val):
            violations.append(f"max {observed_max} > {max_val}")

        expected_parts = []
        if min_val is not None:
            expected_parts.append(f">= {min_val}")
        if max_val is not None:
            expected_parts.append(f"<= {max_val}")
        expected_str = " and ".join(expected_parts)

        if violations:
            return CheckResult(
                check_name="value_range",
                table=table,
                column=column,
                status="fail",
                severity=severity,
                observed_value=f"min={observed_min}, max={observed_max}",
                expected_value=expected_str,
                message="; ".join(violations),
                run_at=datetime.now(timezone.utc),
            )

        return CheckResult(
            check_name="value_range",
            table=table,
            column=column,
            status="pass",
            severity=severity,
            observed_value=f"min={observed_min}, max={observed_max}",
            expected_value=expected_str,
            message=f"values within range [{min_val}, {max_val}]",
            run_at=datetime.now(timezone.utc),
        )
