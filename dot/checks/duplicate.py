from datetime import datetime, timezone

from dot.checks.base import Check, CheckResult


class DuplicateCheck(Check):
    def run(self) -> CheckResult:
        table = self.config["table"]
        severity = self.config.get("severity", "medium")
        table_ref = self.connector.resolve_table(table)
        where = self._where()

        # Support composite grain: 'columns: [a, b, c]' or single 'column: x'
        cols_cfg = self.config.get("columns")
        if cols_cfg:
            columns = [c.strip() for c in cols_cfg] if isinstance(cols_cfg, list) else [cols_cfg.strip()]
        else:
            columns = [self.config["column"]]

        cols_joined = ", ".join(columns)
        label = ", ".join(columns)

        sql = f"""
            SELECT {cols_joined}, COUNT(*) AS cnt
            FROM {table_ref}
            {where}
            GROUP BY {cols_joined}
            HAVING COUNT(*) > 1
        """
        df = self.connector.run_query(sql)
        dup_groups = len(df)

        if dup_groups == 0:
            return CheckResult(
                check_name="duplicate",
                table=table,
                column=label,
                status="pass",
                severity=severity,
                observed_value=0,
                expected_value=0,
                message=f"No duplicates found on ({label})",
                run_at=datetime.now(timezone.utc),
            )

        extra_rows = int(df["cnt"].sum()) - dup_groups
        return CheckResult(
            check_name="duplicate",
            table=table,
            column=label,
            status="fail",
            severity=severity,
            observed_value=dup_groups,
            expected_value=0,
            message=(
                f"{dup_groups} duplicate group{'s' if dup_groups > 1 else ''} on ({label}) "
                f"({extra_rows} extra row{'s' if extra_rows != 1 else ''})"
            ),
            run_at=datetime.now(timezone.utc),
        )
