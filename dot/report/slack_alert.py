from __future__ import annotations

import json
import logging
import os

from dot.checks.base import CheckResult
from dot.report.formatter import (
    format_findings,
    format_run_summary,
    severity_emoji,
    status_header_emoji,
)

logger = logging.getLogger("dot")


def send_slack_alert(
    results: list[CheckResult],
    summary: dict | None,
    slack_cfg: dict,
    source_name: str = "default",
) -> None:
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL")
    if not webhook_url:
        logger.warning("SLACK_WEBHOOK_URL not set — skipping Slack alert")
        return

    notify_on = slack_cfg.get("notify_on", "warn_fail")
    findings = format_findings(results)
    run_summary = format_run_summary(results)

    has_fail = any(r.status in ("fail", "error") for r in results)
    has_warn = any(r.status == "warn" for r in results)

    if notify_on == "warn_fail" and not has_fail and not has_warn:
        return
    if notify_on == "fail_only" and not has_fail:
        return

    header_emoji = status_header_emoji(results)
    if has_fail:
        header_text = f"{header_emoji}  DoT — Failures detected"
    elif has_warn:
        header_text = f"{header_emoji}  DoT — Warnings detected"
    else:
        header_text = f"{header_emoji}  DoT — All checks clean"

    run_at = results[0].run_at.strftime("%Y-%m-%d %H:%M UTC") if results else "—"

    blocks: list[dict] = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": header_text, "emoji": True},
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*Source:* {source_name}\n"
                    f"*Run at:* {run_at}\n"
                    f"*Checks:* {run_summary['total']} total — "
                    f"{run_summary['passed']} pass, {run_summary['warned']} warn, "
                    f"{run_summary['failed']} fail"
                ),
            },
        },
        {"type": "divider"},
    ]

    if summary:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Summary:* {summary.get('overall_status', '')}",
            },
        })

    # Index Claude findings by (table, column, check) for quick lookup
    claude_map = {
        (f.get("table"), f.get("column"), f.get("check")): f
        for f in (summary.get("findings", []) if summary else [])
    }

    for r in findings:
        label = f"{r.table}.{r.column}" if r.column else r.table
        badge = severity_emoji(r.severity)
        cf = claude_map.get((r.table, r.column, r.check_name))

        if cf:
            text = (
                f"*{label} — {r.check_name}* {badge}\n"
                f"{cf['plain_english']}\n"
                f"_Likely cause:_ {cf['likely_cause']}\n"
                f"_Check first:_ {cf['investigate_first']}"
            )
        else:
            text = f"*{label} — {r.check_name}* {badge}\n{r.message}"

        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": text}})

    blocks.append({"type": "divider"})

    next_action = summary.get("next_run_action", "") if summary else ""
    if next_action:
        blocks.append({
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": next_action}],
        })

    _post(webhook_url, blocks)


def _post(webhook_url: str, blocks: list) -> None:
    try:
        import requests

        resp = requests.post(
            webhook_url,
            headers={"Content-Type": "application/json"},
            data=json.dumps({"blocks": blocks}),
            timeout=10,
        )
        if not resp.ok:
            logger.error(f"Slack webhook returned {resp.status_code}: {resp.text}")
    except Exception as exc:
        logger.error(f"Slack alert failed: {exc}", exc_info=True)
