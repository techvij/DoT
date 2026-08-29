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

        # Run-over-run delta: fail if count changes by more than max_delta_pct
        max_delta_pct = self.config.get("max_delta_pct")
        if max_delta_pct is not None and self.store is not None:
            max_delta_pct = float(max_delta_pct)
            history = self.store.get_history(table, "row_count", days=7)
            if not history.empty:
                last_count = float(history["observed_value"].iloc[0])
                if last_count > 0:
                    delta_pct = abs(row_count - last_count) / last_count
                    status = "fail" if delta_pct > max_delta_pct else "pass"
                    return CheckResult(
                        check_name="row_count",
                        table=table,
                        column=None,
                        status=status,
                        severity=severity,
                        observed_value=row_count,
                        expected_value=f"delta <= {max_delta_pct:.0%}",
                        message=(
                            f"{row_count:,} rows ({delta_pct:+.1%} vs last run {last_count:,.0f})"
                        ),
                        run_at=datetime.now(timezone.utc),
                    )
            # No prior run to compare — pass and seed
            return CheckResult(
                check_name="row_count",
                table=table,
                column=None,
                status="pass",
                severity=severity,
                observed_value=row_count,
                expected_value=f"delta <= {max_delta_pct:.0%}",
                message=f"{row_count:,} rows (first run — no prior count to compare)",
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
