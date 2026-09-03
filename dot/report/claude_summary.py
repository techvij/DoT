from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone

from dot.checks.base import CheckResult
from dot.report.formatter import format_findings, format_run_summary

logger = logging.getLogger("dot")

_SYSTEM_PROMPT = (
    "You are a data reliability assistant. You receive the results of a "
    "data quality check run and produce a concise, plain-English diagnostic "
    "summary. You write for a data engineer audience — technical but direct, "
    "no fluff. Never exceed 400 words total."
)

_RESPONSE_SCHEMA = """{
  "overall_status": "string",
  "findings": [
    {
      "table": "string",
      "column": "string or null",
      "check": "string",
      "status": "fail or warn",
      "severity": "string",
      "plain_english": "string — what this means in practice",
      "likely_cause": "string — most probable explanation",
      "investigate_first": "string — specific first action"
    }
  ],
  "next_run_action": "string"
}"""


def _build_prompt(results: list[CheckResult], source_name: str) -> str:
    summary = format_run_summary(results)
    findings = format_findings(results)
    run_at = results[0].run_at if results else datetime.now(timezone.utc)

    lines = [
        f"Here are the results of a DoT check run against {source_name}:\n",
        f"Run at: {run_at.isoformat()}",
        f"Total checks: {summary['total']}   Pass: {summary['passed']}   "
        f"Warn: {summary['warned']}   Fail: {summary['failed']}\n",
    ]

    if findings:
        lines.append("FAILURES AND WARNINGS:")
        for r in findings:
            label = f"{r.table}.{r.column}" if r.column else r.table
            lines.append(
                f"- {label} | {r.check_name} | {r.status} | {r.severity}\n"
                f"  Observed: {r.observed_value}  Expected: {r.expected_value}\n"
                f"  Message: {r.message}"
            )
        lines.append("")

    passing_tables = sorted({r.table for r in results if r.status == "pass"})
    lines.append(
        f"PASSING CHECKS (summary only):\n"
        f"{summary['passed']} checks passed across {passing_tables}\n"
    )

    lines += [
        "Provide:",
        "1. ONE sentence overall status assessment",
        "2. For each failure/warning: what it likely means in practice, "
        "the most probable cause given the check type and observed values, "
        "and the first thing to investigate",
        "3. ONE sentence on what to do before the next run\n",
        "Format your response as JSON only, no markdown, no preamble:",
        _RESPONSE_SCHEMA,
    ]

    return "\n".join(lines)


def generate_claude_summary(results: list[CheckResult], source_name: str) -> dict | None:
    try:
        import anthropic
    except ImportError:
        logger.error("anthropic package not installed — run: pip install anthropic")
        return None

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.error("ANTHROPIC_API_KEY not set — skipping Claude summary")
        return None

    prompt = _build_prompt(results, source_name)

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            temperature=0,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()
        return json.loads(raw)
    except Exception as exc:
        logger.error(f"Claude API call failed: {exc}", exc_info=True)
        return None


def print_claude_summary(summary: dict | None) -> None:
    if not summary:
        return

    print("\n── Claude Diagnosis ──────────────────────────────────────")
    print(f"Overall: {summary.get('overall_status', '')}\n")

    for f in summary.get("findings", []):
        label = f"{f['table']}.{f['column']}" if f.get("column") else f["table"]
        print(f"{label} [{f['check']} / {f['severity'].upper()}]")
        print(f"  What it means: {f['plain_english']}")
        print(f"  Likely cause:  {f['likely_cause']}")
        print(f"  Check first:   {f['investigate_first']}\n")

    if summary.get("next_run_action"):
        print(summary["next_run_action"])
    print("─" * 58)
