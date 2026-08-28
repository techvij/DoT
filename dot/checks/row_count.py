from datetime import datetime, timezone

from dot.checks.base import Check, CheckResult


class RowCountCheck(Check):
    def __init__(self, connector, config: dict, store=None):
        super().__init__(connector, config)
        self.store = store

    def run(self) -> CheckResult:
        table = self.config["table"]
        min_rows = self.config.get("min_rows")
        severity = self.config.get("severity", "medium")
        table_ref = self.connector.resolve_table(table)
        where = self._where()

        sql = f"SELECT COUNT(*) AS row_count FROM {table_ref} {where}"
        df = self.connector.run_query(sql)
        row_count = int(df["row_count"].iloc[0])

        if min_rows is not None:
            min_rows = int(min_rows)
            if row_count >= min_rows:
                return CheckResult(
                    check_name="row_count",
                    table=table,
                    column=None,
                    status="pass",
                    severity=severity,
                    observed_value=row_count,
                    expected_value=f">= {min_rows:,}",
                    message=f"{row_count:,} rows",
                    run_at=datetime.now(timezone.utc),
                )
            else:
                return CheckResult(
                    check_name="row_count",
                    table=table,
                    column=None,
                    status="fail",
                    severity=severity,
                    observed_value=row_count,
                    expected_value=f">= {min_rows:,}",
                    message=f"{row_count:,} rows (minimum: {min_rows:,})",
                    run_at=datetime.now(timezone.utc),
                )

        # Self-calibrating: compare against 7-day rolling average from history
        if self.store is not None:
            history = self.store.get_history(table, "row_count", days=7)
            if not history.empty:
                avg = history["observed_value"].astype(float).mean()
                floor = avg * 0.8
                if row_count < floor:
                    return CheckResult(
                        check_name="row_count",
                        table=table,
                        column=None,
                        status="warn",
                        severity=severity,
                        observed_value=row_count,
                        expected_value=f">= {floor:,.0f}",
                        message=f"{row_count:,} rows, 7d avg {avg:,.0f}",
                        run_at=datetime.now(timezone.utc),
                    )
                else:
                    return CheckResult(
                        check_name="row_count",
                        table=table,
                        column=None,
                        status="pass",
                        severity=severity,
                        observed_value=row_count,
                        expected_value=f">= {floor:,.0f}",
                        message=f"{row_count:,} rows",
                        run_at=datetime.now(timezone.utc),
                    )

        # No history yet — pass and let future runs calibrate
        return CheckResult(
            check_name="row_count",
            table=table,
            column=None,
            status="pass",
            severity=severity,
            observed_value=row_count,
            expected_value=None,
            message=f"{row_count:,} rows (calibrating baseline...)",
            run_at=datetime.now(timezone.utc),
        )
