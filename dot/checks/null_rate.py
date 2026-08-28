from datetime import datetime, timezone

from dot.checks.base import Check, CheckResult


class NullRateCheck(Check):
    def run(self) -> CheckResult:
        table = self.config["table"]
        column = self.config["column"]
        threshold = float(self.config.get("threshold", 0.01))
        severity = self.config.get("severity", "medium")
        table_ref = self.connector.resolve_table(table)
        where = self._where()

        sql = f"""
            SELECT
                {self.connector.cast_float(f'SUM(CASE WHEN {column} IS NULL THEN 1 ELSE 0 END)')}
                / NULLIF(COUNT(*), 0) AS null_rate
            FROM {table_ref}
            {where}
        """
        df = self.connector.run_query(sql)
        raw = df["null_rate"].iloc[0]
        null_rate = float(raw) if raw is not None else 0.0

        status = "pass" if null_rate <= threshold else "fail"
        pct = f"{null_rate:.1%}"
        threshold_pct = f"{threshold:.1%}"

        return CheckResult(
            check_name="null_rate",
            table=table,
            column=column,
            status=status,
            severity=severity,
            observed_value=pct,
            expected_value=f"<= {threshold_pct}",
            message=f"{pct} null" if status == "pass" else f"{pct} null (threshold: {threshold_pct})",
            run_at=datetime.now(timezone.utc),
        )
