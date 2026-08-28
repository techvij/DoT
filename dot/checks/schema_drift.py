from datetime import datetime, timezone

from dot.checks.base import Check, CheckResult


class SchemaDriftCheck(Check):
    def __init__(self, connector, config: dict, store=None):
        super().__init__(connector, config)
        self.store = store

    def run(self) -> CheckResult:
        table = self.config["table"]
        severity = self.config.get("severity", "medium")

        df = self.connector.run_query(self.connector.schema_query(table))
        current = {row["column_name"]: row["data_type"] for _, row in df.iterrows()}

        if self.store is None:
            return CheckResult(
                check_name="schema_drift",
                table=table,
                column=None,
                status="pass",
                severity=severity,
                observed_value=None,
                expected_value=None,
                message="No results store configured — snapshot skipped",
                run_at=datetime.now(timezone.utc),
            )

        snapshot = self.store.get_snapshot(table)

        if snapshot is None:
            self.store.save_snapshot(table, current)
            return CheckResult(
                check_name="schema_drift",
                table=table,
                column=None,
                status="pass",
                severity=severity,
                observed_value=f"{len(current)} cols",
                expected_value=None,
                message="Snapshot saved (baseline established)",
                run_at=datetime.now(timezone.utc),
            )

        added = [c for c in current if c not in snapshot]
        removed = [c for c in snapshot if c not in current]
        type_changes = [
            f"{c}: {snapshot[c]} -> {current[c]}"
            for c in current
            if c in snapshot and current[c] != snapshot[c]
        ]

        diffs = []
        if added:
            diffs.append(f"column{'s' if len(added) > 1 else ''} added: {', '.join(added)}")
        if removed:
            diffs.append(f"column{'s' if len(removed) > 1 else ''} removed: {', '.join(removed)}")
        if type_changes:
            diffs.append(f"type change{'s' if len(type_changes) > 1 else ''}: {'; '.join(type_changes)}")

        if not diffs:
            return CheckResult(
                check_name="schema_drift",
                table=table,
                column=None,
                status="pass",
                severity=severity,
                observed_value=f"{len(current)} cols",
                expected_value=f"{len(snapshot)} cols",
                message="Schema matches baseline",
                run_at=datetime.now(timezone.utc),
            )

        return CheckResult(
            check_name="schema_drift",
            table=table,
            column=None,
            status="fail",
            severity=severity,
            observed_value=f"{len(current)} cols",
            expected_value=f"{len(snapshot)} cols",
            message="; ".join(diffs),
            run_at=datetime.now(timezone.utc),
        )
