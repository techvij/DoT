"""
Regression tests — verify that new features do not alter the core check
pipeline or CLI behaviour. Add one test here for every significant feature.

These run against the CLI via CliRunner (no real DB or network).
"""
import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from dot.__main__ import cli
from dot.checks.base import CheckResult

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_RUNNER_PATH = "dot.__main__.CheckRunner"
_STORE_PATH  = "dot.__main__.ResultsStore"
_LOGGER_PATH = "dot.__main__.setup_logger"


def _result(status="pass", check="null_rate", table="orders", column="status"):
    return CheckResult(
        check_name=check,
        table=table,
        column=column,
        status=status,
        severity="high",
        observed_value=0.01,
        expected_value=0.05,
        message="test result",
        run_at=datetime.now(timezone.utc),
    )


def _mock_runner(results=None, report_cfg=None):
    """Minimal CheckRunner mock."""
    runner = MagicMock()
    runner.run.return_value = results or [
        _result("pass", "null_rate", "orders"),
        _result("fail", "freshness", "events"),
    ]
    runner.config = {
        "connections": {"default": {"type": "postgres"}},
    }
    if report_cfg:
        runner.config["report"] = report_cfg
    return runner


def _invoke(*args, runner_mock=None):
    r = CliRunner()
    with patch(_RUNNER_PATH, return_value=runner_mock or _mock_runner()):
        with patch(_STORE_PATH):
            with patch(_LOGGER_PATH, return_value=(MagicMock(), "dot.log")):
                return r.invoke(cli, list(args))


# ---------------------------------------------------------------------------
# Phase 1 — core check pipeline
# ---------------------------------------------------------------------------

def test_run_exits_zero_with_no_report_config():
    result = _invoke("run", "--config", "config/checks.yaml")
    assert result.exit_code == 0


def test_run_summary_line_present():
    result = _invoke("run", "--config", "config/checks.yaml")
    assert "checks run" in result.output


def test_run_shows_pass_and_fail_icons():
    result = _invoke("run", "--config", "config/checks.yaml")
    output = result.output
    assert ("✓" in output or "OK" in output)
    assert ("✗" in output or "FAIL" in output)


def test_run_table_filter_flag_accepted():
    result = _invoke("run", "--config", "config/checks.yaml", "--table", "orders")
    assert result.exit_code == 0


def test_run_db_flag_accepted():
    result = _invoke("run", "--config", "config/checks.yaml", "--db", "custom.db")
    assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Phase 2a — --output json
# ---------------------------------------------------------------------------

def test_json_output_returns_valid_json():
    result = _invoke("run", "--config", "config/checks.yaml", "--output", "json")
    assert result.exit_code == 0
    parsed = json.loads(result.output)
    assert isinstance(parsed, list)


def test_json_output_contains_expected_keys():
    result = _invoke("run", "--config", "config/checks.yaml", "--output", "json")
    parsed = json.loads(result.output)
    required_keys = {"check_name", "table", "status", "severity", "message", "run_at"}
    assert required_keys.issubset(parsed[0].keys())


def test_json_output_no_human_text_mixed_in():
    result = _invoke("run", "--config", "config/checks.yaml", "--output", "json")
    # Entire stdout must be parseable — no "checks run" line mixed in
    json.loads(result.output)


# ---------------------------------------------------------------------------
# Phase 2b — report layer: --no-claude / --no-slack flags
# ---------------------------------------------------------------------------

def test_no_claude_flag_accepted():
    result = _invoke("run", "--config", "config/checks.yaml", "--no-claude")
    assert result.exit_code == 0


def test_no_slack_flag_accepted():
    result = _invoke("run", "--config", "config/checks.yaml", "--no-slack")
    assert result.exit_code == 0


def test_no_claude_suppresses_generate_call_when_enabled_in_config():
    runner_mock = _mock_runner(report_cfg={"claude": {"enabled": True}})
    r = CliRunner()
    with patch(_RUNNER_PATH, return_value=runner_mock):
        with patch(_STORE_PATH):
            with patch(_LOGGER_PATH, return_value=(MagicMock(), "dot.log")):
                with patch("dot.report.claude_summary.generate_claude_summary") as mock_gen:
                    r.invoke(cli, ["run", "--config", "config/checks.yaml", "--no-claude"])
    mock_gen.assert_not_called()


def test_no_slack_suppresses_send_call_when_enabled_in_config():
    runner_mock = _mock_runner(report_cfg={"slack": {"enabled": True, "notify_on": "always"}})
    r = CliRunner()
    with patch(_RUNNER_PATH, return_value=runner_mock):
        with patch(_STORE_PATH):
            with patch(_LOGGER_PATH, return_value=(MagicMock(), "dot.log")):
                with patch("dot.report.slack_alert.send_slack_alert") as mock_slack:
                    r.invoke(cli, ["run", "--config", "config/checks.yaml", "--no-slack"])
    mock_slack.assert_not_called()


def test_no_report_config_never_calls_claude():
    """If report: section is absent, Claude is never invoked regardless of flags."""
    runner_mock = _mock_runner()  # no report_cfg
    r = CliRunner()
    with patch(_RUNNER_PATH, return_value=runner_mock):
        with patch(_STORE_PATH):
            with patch(_LOGGER_PATH, return_value=(MagicMock(), "dot.log")):
                with patch("dot.report.claude_summary.generate_claude_summary") as mock_gen:
                    r.invoke(cli, ["run", "--config", "config/checks.yaml"])
    mock_gen.assert_not_called()


def test_no_report_config_never_calls_slack():
    """If report: section is absent, Slack is never invoked regardless of flags."""
    runner_mock = _mock_runner()  # no report_cfg
    r = CliRunner()
    with patch(_RUNNER_PATH, return_value=runner_mock):
        with patch(_STORE_PATH):
            with patch(_LOGGER_PATH, return_value=(MagicMock(), "dot.log")):
                with patch("dot.report.slack_alert.send_slack_alert") as mock_slack:
                    r.invoke(cli, ["run", "--config", "config/checks.yaml"])
    mock_slack.assert_not_called()


# ---------------------------------------------------------------------------
# Phase 2b — report layer: failures must never crash the run
# ---------------------------------------------------------------------------

def test_claude_api_failure_does_not_fail_run():
    runner_mock = _mock_runner(report_cfg={"claude": {"enabled": True}})
    r = CliRunner()
    with patch(_RUNNER_PATH, return_value=runner_mock):
        with patch(_STORE_PATH):
            with patch(_LOGGER_PATH, return_value=(MagicMock(), "dot.log")):
                with patch(
                    "dot.report.claude_summary.generate_claude_summary",
                    side_effect=RuntimeError("API down"),
                ):
                    result = r.invoke(cli, ["run", "--config", "config/checks.yaml"])
    assert result.exit_code == 0
    assert "checks run" in result.output


def test_slack_failure_does_not_fail_run():
    runner_mock = _mock_runner(report_cfg={"slack": {"enabled": True, "notify_on": "always"}})
    r = CliRunner()
    with patch(_RUNNER_PATH, return_value=runner_mock):
        with patch(_STORE_PATH):
            with patch(_LOGGER_PATH, return_value=(MagicMock(), "dot.log")):
                with patch(
                    "dot.report.slack_alert.send_slack_alert",
                    side_effect=RuntimeError("webhook down"),
                ):
                    result = r.invoke(cli, ["run", "--config", "config/checks.yaml"])
    assert result.exit_code == 0
    assert "checks run" in result.output
