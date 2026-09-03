"""
Mock-based tests for the report layer (dot/report/).
No real API calls, no network.
"""
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from dot.checks.base import CheckResult
from dot.report.formatter import (
    format_findings,
    format_run_summary,
    severity_emoji,
    status_header_emoji,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _result(status="pass", check="null_rate", table="orders", column="status",
             severity="high", observed=0.01, expected=0.05, message="ok"):
    return CheckResult(
        check_name=check,
        table=table,
        column=column,
        status=status,
        severity=severity,
        observed_value=observed,
        expected_value=expected,
        message=message,
        run_at=datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------------
# Formatter tests
# ---------------------------------------------------------------------------

def test_formatter_sorts_failures_before_warnings():
    results = [
        _result(status="warn",  check="row_count", severity="medium"),
        _result(status="pass",  check="null_rate"),
        _result(status="fail",  check="freshness", severity="critical"),
        _result(status="warn",  check="duplicate",  severity="high"),
        _result(status="fail",  check="value_range", severity="high"),
    ]
    findings = format_findings(results)
    statuses = [r.status for r in findings]
    # All fails come before all warns
    last_fail_idx = max(i for i, r in enumerate(findings) if r.status == "fail")
    first_warn_idx = min(i for i, r in enumerate(findings) if r.status == "warn")
    assert last_fail_idx < first_warn_idx
    # pass not included
    assert "pass" not in statuses


def test_formatter_severity_emoji_mapping():
    assert severity_emoji("critical") == "🔴"
    assert severity_emoji("high")     == "🔴"
    assert severity_emoji("medium")   == "🟡"
    assert severity_emoji("low")      == "🟢"
    assert severity_emoji("unknown")  == "🟢"


def test_formatter_status_header_emoji_all_pass():
    results = [_result(status="pass"), _result(status="pass")]
    assert status_header_emoji(results) == "✅"


def test_formatter_status_header_emoji_fail():
    results = [_result(status="pass"), _result(status="fail")]
    assert status_header_emoji(results) == "🔴"


def test_formatter_status_header_emoji_warn_only():
    results = [_result(status="pass"), _result(status="warn")]
    assert status_header_emoji(results) == "⚠️"


def test_formatter_run_summary_counts():
    results = [
        _result(status="pass"),
        _result(status="pass"),
        _result(status="warn"),
        _result(status="fail"),
    ]
    s = format_run_summary(results)
    assert s["total"]  == 4
    assert s["passed"] == 2
    assert s["warned"] == 1
    assert s["failed"] == 1


# ---------------------------------------------------------------------------
# Claude summary tests
# ---------------------------------------------------------------------------

def test_claude_summary_structures_prompt_correctly():
    """The prompt sent to Claude must include table name, check name, and message."""
    from dot.report.claude_summary import generate_claude_summary

    fake_response_json = (
        '{"overall_status": "ok", "findings": [], "next_run_action": "monitor"}'
    )
    mock_message = MagicMock()
    mock_message.content = [MagicMock(text=fake_response_json)]

    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_message

    results = [
        _result(status="fail", check="null_rate", table="orders",
                column="status", message="5.6% null", observed=0.056),
        _result(status="pass", check="row_count", table="orders", column=None),
    ]

    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
        with patch("anthropic.Anthropic", return_value=mock_client):
            summary = generate_claude_summary(results, "postgres")

    assert summary is not None
    call_kwargs = mock_client.messages.create.call_args[1]
    user_content = call_kwargs["messages"][0]["content"]
    assert "orders" in user_content
    assert "null_rate" in user_content
    assert "5.6% null" in user_content
    assert call_kwargs["model"] == "claude-sonnet-4-6"
    assert call_kwargs["temperature"] == 0


def test_claude_summary_handles_api_failure_gracefully():
    """If the API raises, generate_claude_summary returns None and does not crash."""
    from dot.report.claude_summary import generate_claude_summary

    mock_client = MagicMock()
    mock_client.messages.create.side_effect = RuntimeError("network timeout")

    results = [_result(status="fail")]

    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
        with patch("anthropic.Anthropic", return_value=mock_client):
            summary = generate_claude_summary(results, "postgres")

    assert summary is None


def test_claude_summary_returns_none_without_api_key():
    """Missing ANTHROPIC_API_KEY should return None silently."""
    from dot.report.claude_summary import generate_claude_summary

    results = [_result(status="fail")]

    with patch.dict("os.environ", {}, clear=True):
        # Make sure ANTHROPIC_API_KEY is absent
        import os
        os.environ.pop("ANTHROPIC_API_KEY", None)
        with patch("anthropic.Anthropic") as mock_cls:
            summary = generate_claude_summary(results, "postgres")

    assert summary is None
    mock_cls.assert_not_called()


# ---------------------------------------------------------------------------
# Slack alert tests
# ---------------------------------------------------------------------------

def test_slack_payload_structure():
    """Slack POST body must include a header block and a section with source info."""
    from dot.report.slack_alert import send_slack_alert

    results = [
        _result(status="fail", check="freshness", table="events", column="created_at",
                message="stale", severity="critical"),
    ]

    with patch.dict("os.environ", {"SLACK_WEBHOOK_URL": "https://hooks.slack.com/test"}):
        with patch("requests.post") as mock_post:
            mock_post.return_value = MagicMock(ok=True)
            send_slack_alert(results, None, {"notify_on": "always"}, source_name="postgres")

    mock_post.assert_called_once()
    payload = mock_post.call_args[1]["data"]
    blocks = __import__("json").loads(payload)["blocks"]

    block_types = [b["type"] for b in blocks]
    assert "header" in block_types
    assert "section" in block_types

    header = next(b for b in blocks if b["type"] == "header")
    assert "DoT" in header["text"]["text"]


def test_slack_notify_on_warn_fail_skips_clean_run():
    """notify_on=warn_fail must not POST when all checks pass."""
    from dot.report.slack_alert import send_slack_alert

    results = [_result(status="pass"), _result(status="pass")]

    with patch.dict("os.environ", {"SLACK_WEBHOOK_URL": "https://hooks.slack.com/test"}):
        with patch("requests.post") as mock_post:
            send_slack_alert(results, None, {"notify_on": "warn_fail"})

    mock_post.assert_not_called()


def test_slack_notify_on_always_sends_clean_run():
    """notify_on=always must POST even when all checks pass."""
    from dot.report.slack_alert import send_slack_alert

    results = [_result(status="pass"), _result(status="pass")]

    with patch.dict("os.environ", {"SLACK_WEBHOOK_URL": "https://hooks.slack.com/test"}):
        with patch("requests.post") as mock_post:
            mock_post.return_value = MagicMock(ok=True)
            send_slack_alert(results, None, {"notify_on": "always"})

    mock_post.assert_called_once()


def test_slack_skips_silently_without_webhook_url():
    """Missing SLACK_WEBHOOK_URL must not raise."""
    from dot.report.slack_alert import send_slack_alert

    results = [_result(status="fail")]

    with patch.dict("os.environ", {}, clear=True):
        import os
        os.environ.pop("SLACK_WEBHOOK_URL", None)
        with patch("requests.post") as mock_post:
            send_slack_alert(results, None, {"notify_on": "always"})

    mock_post.assert_not_called()
