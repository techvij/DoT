from datetime import datetime, timezone

from dot.checks.base import Check, CheckResult


class RegexCheck(Check):
    """
    Validate that all non-null values in a column match a regex pattern.
    Uses database-native regex: ~ operator on Postgres, REGEXP_CONTAINS on BigQuery.
    """

    def run(self) -> CheckResult:
        table = self.config["table"]
        column = self.config["column"]
        pattern = self.config["pattern"]
        severity = self.config.get("severity", "medium")
        table_ref = self.connector.resolve_table(table)
        col_as_str = self.connector.cast_string(column)

        not_matching = f"{column} IS NOT NULL AND NOT ({self.connector.regex_match(col_as_str, pattern)})"
        where = self._where(extra=not_matching)

        sql = f"""
            SELECT {col_as_str} AS val, COUNT(*) AS cnt
            FROM {table_ref}
            {where}
            GROUP BY {col_as_str}
            ORDER BY cnt DESC
        """
        df = self.connector.run_query(sql)
        violation_groups = len(df)
        total_rows = int(df["cnt"].sum()) if not df.empty else 0

        if violation_groups == 0:
            return CheckResult(
                check_name="regex",
                table=table,
                column=column,
                status="pass",
                severity=severity,
                observed_value=0,
                expected_value=f"matches {pattern}",
                message=f"all non-null values match pattern '{pattern}'",
                run_at=datetime.now(timezone.utc),
            )

        examples = df["val"].tolist()[:5]
        quoted = ", ".join(f"'{v}'" for v in examples)
        suffix = f" (+{violation_groups - 5} more)" if violation_groups > 5 else ""

        return CheckResult(
            check_name="regex",
            table=table,
            column=column,
            status="fail",
            severity=severity,
            observed_value=total_rows,
            expected_value=f"matches {pattern}",
            message=f"{total_rows} row{'s' if total_rows != 1 else ''} don't match '{pattern}': {quoted}{suffix}",
            run_at=datetime.now(timezone.utc),
        )
