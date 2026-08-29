"""Tests for partition clause builder — no database required."""
import pytest
from unittest.mock import MagicMock

from dot.checks.base import Check


class _ConcreteCheck(Check):
    def run(self):
        pass


def _make(config: dict) -> _ConcreteCheck:
    return _ConcreteCheck(MagicMock(), config)


def test_no_partition_returns_empty():
    check = _make({"table": "t"})
    assert check._partition_clause() == ""
    assert check._where() == ""


def test_single_partition():
    check = _make({"table": "t", "partition_column": "dt", "partition_value": "2026-01-01"})
    assert check._partition_clause() == "dt = '2026-01-01'"
    assert check._where() == "WHERE dt = '2026-01-01'"


def test_composite_partition():
    check = _make({
        "table": "t",
        "partition_column": "year/month/day",
        "partition_value": "2026/05/01",
    })
    assert check._partition_clause() == "year = '2026' AND month = '05' AND day = '01'"


def test_composite_partition_in_where():
    check = _make({
        "table": "t",
        "partition_column": "year/month",
        "partition_value": "2026/05",
    })
    result = check._where(extra="col IS NOT NULL")
    assert result == "WHERE year = '2026' AND month = '05' AND col IS NOT NULL"


def test_extra_filter_only():
    check = _make({"table": "t"})
    assert check._where(extra="col IS NOT NULL") == "WHERE col IS NOT NULL"


def test_mismatched_partition_raises():
    check = _make({
        "table": "t",
        "partition_column": "year/month",
        "partition_value": "2026",
    })
    with pytest.raises(ValueError, match="partition_column has 2"):
        check._partition_clause()
