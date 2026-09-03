from __future__ import annotations

from dot.checks.base import CheckResult

_SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}
_SEVERITY_EMOJI = {"critical": "🔴", "high": "🔴", "medium": "🟡", "low": "🟢"}


def format_run_summary(results: list[CheckResult]) -> dict:
    return {
        "total":   len(results),
        "passed":  sum(1 for r in results if r.status == "pass"),
        "warned":  sum(1 for r in results if r.status == "warn"),
        "failed":  sum(1 for r in results if r.status == "fail"),
        "errored": sum(1 for r in results if r.status == "error"),
        "tables":  sorted({r.table for r in results}),
    }


def format_findings(results: list[CheckResult]) -> list[CheckResult]:
    """Non-pass results: failures/errors first, then warnings; each group sorted by severity."""
    non_pass = [r for r in results if r.status in ("fail", "error", "warn")]
    return sorted(
        non_pass,
        key=lambda r: (
            0 if r.status in ("fail", "error") else 1,
            _SEVERITY_ORDER.get(r.severity, 9),
        ),
    )


def severity_emoji(severity: str) -> str:
    return _SEVERITY_EMOJI.get(severity, "🟢")


def status_header_emoji(results: list[CheckResult]) -> str:
    statuses = {r.status for r in results}
    if "fail" in statuses or "error" in statuses:
        return "🔴"
    if "warn" in statuses:
        return "⚠️"
    return "✅"
