from datetime import datetime, timezone

from dot.checks.base import Check, CheckResult


class FreshnessCheck(Check):
    def run(self) -> CheckResult:
        table = self.config["table"]
        column = self.config["column"]
        max_age_hours = float(self.config.get("max_age_hours", 24))
        severity = self.config.get("severity", "medium")
        where = self._where()

        sql = f"SELECT MAX({column}) AS latest FROM {table} {where}"
        df = self.connector.run_query(sql)
        latest = df["latest"].iloc[0]

        if latest is None:
            return CheckResult(
                check_name="freshness",
                table=table,
                column=column,
                status="fail",
                severity=severity,
                observed_value=None,
                expected_value=f"<= {max_age_hours}h old",
                message="No data found in table",
                run_at=datetime.now(timezone.utc),
            )

        # Normalize to a plain Python datetime, handling both aware and naive timestamps
        if hasattr(latest, "to_pydatetime"):
            latest = latest.to_pydatetime()

        now_utc = datetime.now(timezone.utc)
        if latest.tzinfo is not None:
            age_seconds = (now_utc - latest).total_seconds()
        else:
            age_seconds = (datetime.utcnow() - latest).total_seconds()

        age_hours = age_seconds / 3600
        status = "pass" if age_hours <= max_age_hours else "fail"

        if status == "pass":
            msg = f"last record {age_hours:.1f}h ago"
        else:
            msg = f"last record {age_hours:.1f}h ago, threshold {max_age_hours}h"

        return CheckResult(
            check_name="freshness",
            table=table,
            column=column,
            status=status,
            severity=severity,
            observed_value=f"{age_hours:.1f}h ago",
            expected_value=f"<= {max_age_hours}h old",
            message=msg,
            run_at=datetime.now(timezone.utc),
        )
