from datetime import datetime, timezone

from dot.checks.base import Check, CheckResult


class DuplicateCheck(Check):
    def run(self) -> CheckResult:
        table = self.config["table"]
        column = self.config["column"]
        severity = self.config.get("severity", "medium")
        where = self._where()

        sql = f"""
            SELECT {column}, COUNT(*) AS cnt
            FROM {table}
            {where}
            GROUP BY {column}
            HAVING COUNT(*) > 1
        """
        df = self.connector.run_query(sql)
        dup_values = len(df)

        if dup_values == 0:
            return CheckResult(
                check_name="duplicate",
                table=table,
                column=column,
                status="pass",
                severity=severity,
                observed_value=0,
                expected_value=0,
                message="No duplicates found",
                run_at=datetime.now(timezone.utc),
            )

        # Extra rows = total duplicate occurrences minus the "first" of each group
        extra_rows = int(df["cnt"].sum()) - dup_values
        return CheckResult(
            check_name="duplicate",
            table=table,
            column=column,
            status="fail",
            severity=severity,
            observed_value=dup_values,
            expected_value=0,
            message=(
                f"{dup_values} duplicate value{'s' if dup_values > 1 else ''} in {column} "
                f"({extra_rows} extra row{'s' if extra_rows != 1 else ''})"
            ),
            run_at=datetime.now(timezone.utc),
        )
