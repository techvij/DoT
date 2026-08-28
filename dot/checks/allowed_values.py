from datetime import datetime, timezone

from dot.checks.base import Check, CheckResult


class AllowedValuesCheck(Check):
    def run(self) -> CheckResult:
        table = self.config["table"]
        column = self.config["column"]
        severity = self.config.get("severity", "medium")
        raw_values = str(self.config.get("values", ""))
        allowed = [v.strip() for v in raw_values.split(",") if v.strip()]

        if not allowed:
            return CheckResult(
                check_name="allowed_values",
                table=table,
                column=column,
                status="fail",
                severity=severity,
                observed_value=None,
                expected_value=None,
                message="No allowed values configured — check your YAML (values: a,b,c)",
                run_at=datetime.now(timezone.utc),
            )

        not_in = ", ".join(f"'{v}'" for v in allowed)
        # Exclude NULLs — null_rate covers those separately
        column_filter = f"{column} IS NOT NULL AND {column}::TEXT NOT IN ({not_in})"
        where = self._where(extra=column_filter)

        sql = f"""
            SELECT {column}::TEXT AS val, COUNT(*) AS cnt
            FROM {table}
            {where}
            GROUP BY {column}::TEXT
            ORDER BY cnt DESC
        """
        df = self.connector.run_query(sql)

        if df.empty:
            return CheckResult(
                check_name="allowed_values",
                table=table,
                column=column,
                status="pass",
                severity=severity,
                observed_value=None,
                expected_value=", ".join(allowed),
                message=f"all values in allowed set ({len(allowed)} values)",
                run_at=datetime.now(timezone.utc),
            )

        unexpected = df["val"].tolist()
        total_rows = int(df["cnt"].sum())
        quoted = ", ".join(f"'{v}'" for v in unexpected[:5])
        suffix = f" (+{len(unexpected) - 5} more)" if len(unexpected) > 5 else ""

        return CheckResult(
            check_name="allowed_values",
            table=table,
            column=column,
            status="fail",
            severity=severity,
            observed_value=f"{len(unexpected)} unexpected value(s)",
            expected_value=", ".join(allowed),
            message=(
                f"{len(unexpected)} unexpected value(s) found: {quoted}{suffix} "
                f"({total_rows} row{'s' if total_rows != 1 else ''} total)"
            ),
            run_at=datetime.now(timezone.utc),
        )
