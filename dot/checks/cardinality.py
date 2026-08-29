from datetime import datetime, timezone

from dot.checks.base import Check, CheckResult


class CardinalityCheck(Check):
    """
    COUNT(DISTINCT column) must stay within [min_distinct, max_distinct].
    Catches dimension load failures where a bad DELETE+INSERT silently collapses
    the number of distinct values (e.g. a category column drops from 20 to 3).
    """

    def run(self) -> CheckResult:
        table = self.config["table"]
        column = self.config["column"]
        min_distinct = self.config.get("min_distinct")
        max_distinct = self.config.get("max_distinct")
        severity = self.config.get("severity", "medium")
        table_ref = self.connector.resolve_table(table)
        where = self._where()

        sql = f"SELECT COUNT(DISTINCT {column}) AS distinct_count FROM {table_ref} {where}"
        df = self.connector.run_query(sql)
        distinct = int(df["distinct_count"].iloc[0])

        violations = []
        if min_distinct is not None and distinct < int(min_distinct):
            violations.append(f"< min {min_distinct}")
        if max_distinct is not None and distinct > int(max_distinct):
            violations.append(f"> max {max_distinct}")

        bounds = " and ".join(
            filter(None, [
                f">= {min_distinct}" if min_distinct is not None else "",
                f"<= {max_distinct}" if max_distinct is not None else "",
            ])
        )

        if violations:
            return CheckResult(
                check_name="cardinality",
                table=table,
                column=column,
                status="fail",
                severity=severity,
                observed_value=distinct,
                expected_value=bounds,
                message=f"{distinct} distinct values ({'; '.join(violations)})",
                run_at=datetime.now(timezone.utc),
            )

        return CheckResult(
            check_name="cardinality",
            table=table,
            column=column,
            status="pass",
            severity=severity,
            observed_value=distinct,
            expected_value=bounds,
            message=f"{distinct} distinct values",
            run_at=datetime.now(timezone.utc),
        )
