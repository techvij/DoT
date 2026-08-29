from datetime import datetime, timezone

from dot.checks.base import Check, CheckResult


class CustomSQLCheck(Check):
    """
    Run any SQL and assert the result equals an expected value.
    The SQL must return a single row with a single column.
    Use {table} in the SQL as a placeholder — it gets resolved via the connector's
    resolve_table() so dialect quoting (e.g. BQ backticks) is applied automatically.
    """

    def run(self) -> CheckResult:
        table = self.config["table"]
        sql_template = self.config["sql"]
        expect = self.config.get("expect", 0)
        severity = self.config.get("severity", "medium")

        table_ref = self.connector.resolve_table(table)
        sql = sql_template.replace("{table}", table_ref)

        df = self.connector.run_query(sql)
        actual = df.iloc[0, 0]

        try:
            status = "pass" if float(actual) == float(expect) else "fail"
        except (TypeError, ValueError):
            status = "pass" if str(actual) == str(expect) else "fail"

        return CheckResult(
            check_name="custom_sql",
            table=table,
            column=None,
            status=status,
            severity=severity,
            observed_value=actual,
            expected_value=expect,
            message=(
                f"result: {actual}"
                if status == "pass"
                else f"expected {expect}, got {actual}"
            ),
            run_at=datetime.now(timezone.utc),
        )
