from datetime import datetime, timezone

from dot.checks.base import Check, CheckResult


class AllowedValuesCheck(Check):
    def run(self) -> CheckResult:
        table = self.config["table"]
        column = self.config["column"]
        severity = self.config.get("severity", "medium")
        raw_values = str(self.config.get("values", ""))
        allowed = [v.strip() for v in raw_values.split(",") if v.strip()]
        require_all = bool(self.config.get("require_all", False))
        table_ref = self.connector.resolve_table(table)
        col_as_str = self.connector.cast_string(column)

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

        # Query 1: unexpected non-null values (NOT in the allowed set)
        not_in = ", ".join(f"'{v}'" for v in allowed)
        unexpected_filter = f"{column} IS NOT NULL AND {col_as_str} NOT IN ({not_in})"
        where_unexpected = self._where(extra=unexpected_filter)

        sql_unexpected = f"""
            SELECT {col_as_str} AS val, COUNT(*) AS cnt
            FROM {table_ref}
            {where_unexpected}
            GROUP BY {col_as_str}
            ORDER BY cnt DESC
        """
        df_unexpected = self.connector.run_query(sql_unexpected)
        unexpected_vals = df_unexpected["val"].tolist() if not df_unexpected.empty else []
        total_unexpected_rows = int(df_unexpected["cnt"].sum()) if not df_unexpected.empty else 0

        # Query 2 (require_all only): find which allowed values are absent from the data
        absent = []
        if require_all:
            where_present = self._where(extra=f"{column} IS NOT NULL")
            sql_present = f"""
                SELECT DISTINCT {col_as_str} AS val
                FROM {table_ref}
                {where_present}
            """
            df_present = self.connector.run_query(sql_present)
            present = set(df_present["val"].tolist())
            absent = [v for v in allowed if v not in present]

        # Build violation messages
        violations = []
        if unexpected_vals:
            quoted = ", ".join(f"'{v}'" for v in unexpected_vals[:5])
            suffix = f" (+{len(unexpected_vals) - 5} more)" if len(unexpected_vals) > 5 else ""
            violations.append(
                f"{len(unexpected_vals)} unexpected value(s) found: {quoted}{suffix} "
                f"({total_unexpected_rows} row{'s' if total_unexpected_rows != 1 else ''} total)"
            )
        if absent:
            violations.append(f"expected value(s) absent: {', '.join(f'{chr(39)}{v}{chr(39)}' for v in absent)}")

        if not violations:
            suffix = " — all values present in data" if require_all else ""
            return CheckResult(
                check_name="allowed_values",
                table=table,
                column=column,
                status="pass",
                severity=severity,
                observed_value=None,
                expected_value=", ".join(allowed),
                message=f"all values in allowed set ({len(allowed)} values){suffix}",
                run_at=datetime.now(timezone.utc),
            )

        return CheckResult(
            check_name="allowed_values",
            table=table,
            column=column,
            status="fail",
            severity=severity,
            observed_value=(
                f"{len(unexpected_vals)} unexpected" if unexpected_vals else f"{len(absent)} absent"
            ),
            expected_value=", ".join(allowed),
            message="; ".join(violations),
            run_at=datetime.now(timezone.utc),
        )
