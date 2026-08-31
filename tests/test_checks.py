"""
Mock-connector tests for all check types.
No database required — the connector is a MagicMock.
"""
from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock

import pandas as pd
import pytest

from dot.checks.allowed_values import AllowedValuesCheck
from dot.checks.cardinality import CardinalityCheck
from dot.checks.custom_sql import CustomSQLCheck
from dot.checks.duplicate import DuplicateCheck
from dot.checks.freshness import FreshnessCheck
from dot.checks.null_rate import NullRateCheck
from dot.checks.regex_check import RegexCheck
from dot.checks.row_count import RowCountCheck
from dot.checks.schema_drift import SchemaDriftCheck
from dot.checks.value_range import ValueRangeCheck


# ---------------------------------------------------------------------------
# Shared fixture
# ---------------------------------------------------------------------------

def make_connector():
    """Mock connector with Postgres-style dialect defaults."""
    c = MagicMock()
    c.resolve_table.side_effect = lambda t: t
    c.cast_string.side_effect = lambda col: f"{col}::TEXT"
    c.cast_float.side_effect = lambda col: f"CAST({col} AS FLOAT)"
    c.regex_match.side_effect = lambda expr, pat: f"{expr} ~ '{pat}'"
    return c


# ---------------------------------------------------------------------------
# NullRateCheck
# ---------------------------------------------------------------------------

def test_null_rate_pass():
    c = make_connector()
    c.run_query.return_value = pd.DataFrame({"null_rate": [0.005]})
    result = NullRateCheck(c, {"table": "orders", "column": "status", "threshold": 0.01, "severity": "high"}).run()
    assert result.status == "pass"
    assert result.check_name == "null_rate"


def test_null_rate_fail():
    c = make_connector()
    c.run_query.return_value = pd.DataFrame({"null_rate": [0.055]})
    result = NullRateCheck(c, {"table": "orders", "column": "status", "threshold": 0.01, "severity": "high"}).run()
    assert result.status == "fail"
    assert "5.5%" in result.message


def test_null_rate_none_treated_as_zero():
    c = make_connector()
    c.run_query.return_value = pd.DataFrame({"null_rate": [None]})
    result = NullRateCheck(c, {"table": "orders", "column": "status", "threshold": 0.01, "severity": "medium"}).run()
    assert result.status == "pass"


# ---------------------------------------------------------------------------
# ValueRangeCheck
# ---------------------------------------------------------------------------

def test_value_range_pass():
    c = make_connector()
    c.run_query.return_value = pd.DataFrame({"min_val": [10], "max_val": [900]})
    result = ValueRangeCheck(c, {"table": "payments", "column": "amount", "min": 0, "max": 1000, "severity": "high"}).run()
    assert result.status == "pass"


def test_value_range_fail_min():
    c = make_connector()
    c.run_query.return_value = pd.DataFrame({"min_val": [-50], "max_val": [900]})
    result = ValueRangeCheck(c, {"table": "payments", "column": "amount", "min": 0, "max": 1000, "severity": "high"}).run()
    assert result.status == "fail"
    assert "min" in result.message


def test_value_range_fail_max():
    c = make_connector()
    c.run_query.return_value = pd.DataFrame({"min_val": [10], "max_val": [1500]})
    result = ValueRangeCheck(c, {"table": "payments", "column": "amount", "min": 0, "max": 1000, "severity": "high"}).run()
    assert result.status == "fail"
    assert "max" in result.message


def test_value_range_empty_table():
    c = make_connector()
    c.run_query.return_value = pd.DataFrame({"min_val": [None], "max_val": [None]})
    result = ValueRangeCheck(c, {"table": "payments", "column": "amount", "min": 0, "severity": "medium"}).run()
    assert result.status == "pass"


# ---------------------------------------------------------------------------
# FreshnessCheck
# ---------------------------------------------------------------------------

def test_freshness_pass_naive_datetime():
    c = make_connector()
    recent = datetime.utcnow() - timedelta(hours=2)
    c.run_query.return_value = pd.DataFrame({"latest": [recent]})
    result = FreshnessCheck(c, {"table": "events", "column": "created_at", "max_age_hours": 6, "severity": "high"}).run()
    assert result.status == "pass"


def test_freshness_fail_naive_datetime():
    c = make_connector()
    stale = datetime.utcnow() - timedelta(hours=10)
    c.run_query.return_value = pd.DataFrame({"latest": [stale]})
    result = FreshnessCheck(c, {"table": "events", "column": "created_at", "max_age_hours": 6, "severity": "high"}).run()
    assert result.status == "fail"
    assert "threshold" in result.message


def test_freshness_pass_aware_datetime():
    c = make_connector()
    recent = datetime.now(timezone.utc) - timedelta(hours=1)
    c.run_query.return_value = pd.DataFrame({"latest": [recent]})
    result = FreshnessCheck(c, {"table": "events", "column": "created_at", "max_age_hours": 6, "severity": "high"}).run()
    assert result.status == "pass"


def test_freshness_fail_date_string():
    c = make_connector()
    c.run_query.return_value = pd.DataFrame({"latest": ["2020-01-01"]})
    result = FreshnessCheck(c, {"table": "events", "column": "dt", "max_age_hours": 24, "severity": "high"}).run()
    assert result.status == "fail"


def test_freshness_fail_date_object():
    c = make_connector()
    c.run_query.return_value = pd.DataFrame({"latest": [date(2020, 1, 1)]})
    result = FreshnessCheck(c, {"table": "events", "column": "dt", "max_age_hours": 24, "severity": "high"}).run()
    assert result.status == "fail"


def test_freshness_empty_table():
    c = make_connector()
    c.run_query.return_value = pd.DataFrame({"latest": [None]})
    result = FreshnessCheck(c, {"table": "events", "column": "created_at", "max_age_hours": 6, "severity": "high"}).run()
    assert result.status == "fail"
    assert "No data" in result.message


# ---------------------------------------------------------------------------
# DuplicateCheck
# ---------------------------------------------------------------------------

def test_duplicate_pass():
    c = make_connector()
    c.run_query.return_value = pd.DataFrame(columns=["order_id", "cnt"])
    result = DuplicateCheck(c, {"table": "orders", "column": "order_id", "severity": "high"}).run()
    assert result.status == "pass"


def test_duplicate_fail():
    c = make_connector()
    c.run_query.return_value = pd.DataFrame({"order_id": ["A", "B"], "cnt": [3, 2]})
    result = DuplicateCheck(c, {"table": "orders", "column": "order_id", "severity": "high"}).run()
    assert result.status == "fail"
    assert "2 duplicate groups" in result.message


def test_duplicate_composite_pass():
    c = make_connector()
    c.run_query.return_value = pd.DataFrame(columns=["order_id", "product_id", "cnt"])
    result = DuplicateCheck(c, {"table": "order_items", "columns": ["order_id", "product_id"], "severity": "high"}).run()
    assert result.status == "pass"


def test_duplicate_composite_fail():
    c = make_connector()
    c.run_query.return_value = pd.DataFrame({"order_id": ["A"], "product_id": ["X"], "cnt": [2]})
    result = DuplicateCheck(c, {"table": "order_items", "columns": ["order_id", "product_id"], "severity": "high"}).run()
    assert result.status == "fail"
    assert "order_id, product_id" in result.column


# ---------------------------------------------------------------------------
# SchemaDriftCheck
# ---------------------------------------------------------------------------

def _schema_df(*cols):
    return pd.DataFrame({
        "column_name": list(cols),
        "data_type": ["text"] * len(cols),
    })


def test_schema_drift_first_run():
    c = make_connector()
    c.run_query.return_value = _schema_df("id", "name", "email")
    store = MagicMock()
    store.get_snapshot.return_value = None
    result = SchemaDriftCheck(c, {"table": "users", "severity": "medium"}, store=store).run()
    assert result.status == "pass"
    assert "Snapshot saved" in result.message
    store.save_snapshot.assert_called_once()


def test_schema_drift_no_change():
    c = make_connector()
    c.run_query.return_value = _schema_df("id", "name")
    store = MagicMock()
    store.get_snapshot.return_value = {"id": "text", "name": "text"}
    result = SchemaDriftCheck(c, {"table": "users", "severity": "medium"}, store=store).run()
    assert result.status == "pass"


def test_schema_drift_column_added():
    c = make_connector()
    c.run_query.return_value = _schema_df("id", "name", "phone")
    store = MagicMock()
    store.get_snapshot.return_value = {"id": "text", "name": "text"}
    result = SchemaDriftCheck(c, {"table": "users", "severity": "medium"}, store=store).run()
    assert result.status == "fail"
    assert "phone" in result.message


def test_schema_drift_column_removed():
    c = make_connector()
    c.run_query.return_value = _schema_df("id")
    store = MagicMock()
    store.get_snapshot.return_value = {"id": "text", "name": "text"}
    result = SchemaDriftCheck(c, {"table": "users", "severity": "medium"}, store=store).run()
    assert result.status == "fail"
    assert "name" in result.message


# ---------------------------------------------------------------------------
# AllowedValuesCheck
# ---------------------------------------------------------------------------

def test_allowed_values_pass():
    c = make_connector()
    c.run_query.return_value = pd.DataFrame(columns=["val", "cnt"])
    result = AllowedValuesCheck(c, {"table": "orders", "column": "status", "values": "active,inactive", "severity": "medium"}).run()
    assert result.status == "pass"


def test_allowed_values_fail_unexpected():
    c = make_connector()
    c.run_query.return_value = pd.DataFrame({"val": ["unknown"], "cnt": [5]})
    result = AllowedValuesCheck(c, {"table": "orders", "column": "status", "values": "active,inactive", "severity": "medium"}).run()
    assert result.status == "fail"
    assert "unexpected" in result.message


def test_allowed_values_require_all_absent():
    c = make_connector()
    c.run_query.side_effect = [
        pd.DataFrame(columns=["val", "cnt"]),      # no unexpected values
        pd.DataFrame({"val": ["active"]}),          # only "active" present, "inactive" absent
    ]
    result = AllowedValuesCheck(c, {"table": "orders", "column": "status", "values": "active,inactive", "require_all": True, "severity": "medium"}).run()
    assert result.status == "fail"
    assert "absent" in result.message


def test_allowed_values_no_values_configured():
    c = make_connector()
    result = AllowedValuesCheck(c, {"table": "orders", "column": "status", "severity": "medium"}).run()
    assert result.status == "fail"
    assert "No allowed values" in result.message


# ---------------------------------------------------------------------------
# CardinalityCheck
# ---------------------------------------------------------------------------

def test_cardinality_pass():
    c = make_connector()
    c.run_query.return_value = pd.DataFrame({"distinct_count": [30]})
    result = CardinalityCheck(c, {"table": "products", "column": "category", "min_distinct": 5, "max_distinct": 50, "severity": "high"}).run()
    assert result.status == "pass"
    assert "30" in result.message


def test_cardinality_fail_below_min():
    c = make_connector()
    c.run_query.return_value = pd.DataFrame({"distinct_count": [3]})
    result = CardinalityCheck(c, {"table": "products", "column": "category", "min_distinct": 5, "severity": "high"}).run()
    assert result.status == "fail"
    assert "< min" in result.message


def test_cardinality_fail_above_max():
    c = make_connector()
    c.run_query.return_value = pd.DataFrame({"distinct_count": [60]})
    result = CardinalityCheck(c, {"table": "products", "column": "category", "max_distinct": 50, "severity": "high"}).run()
    assert result.status == "fail"
    assert "> max" in result.message


# ---------------------------------------------------------------------------
# CustomSQLCheck
# ---------------------------------------------------------------------------

def test_custom_sql_pass():
    c = make_connector()
    c.run_query.return_value = pd.DataFrame({"result": [0]})
    result = CustomSQLCheck(c, {"table": "orders", "sql": "SELECT COUNT(*) FROM {table} WHERE x IS NULL", "expect": 0, "severity": "high"}).run()
    assert result.status == "pass"


def test_custom_sql_fail():
    c = make_connector()
    c.run_query.return_value = pd.DataFrame({"result": [7]})
    result = CustomSQLCheck(c, {"table": "orders", "sql": "SELECT COUNT(*) FROM {table} WHERE x IS NULL", "expect": 0, "severity": "high"}).run()
    assert result.status == "fail"
    assert "expected 0, got 7" in result.message


def test_custom_sql_table_placeholder_resolved():
    c = make_connector()
    c.resolve_table.side_effect = None
    c.resolve_table.return_value = "`my-project.ds.orders`"
    c.run_query.return_value = pd.DataFrame({"result": [0]})
    CustomSQLCheck(c, {"table": "orders", "sql": "SELECT 1 FROM {table}", "expect": 0, "severity": "low"}).run()
    call_sql = c.run_query.call_args[0][0]
    assert "`my-project.ds.orders`" in call_sql


# ---------------------------------------------------------------------------
# RegexCheck
# ---------------------------------------------------------------------------

def test_regex_pass():
    c = make_connector()
    c.run_query.return_value = pd.DataFrame(columns=["val", "cnt"])
    result = RegexCheck(c, {"table": "users", "column": "email", "pattern": r"^[^@]+@[^@]+\.[^@]+$", "severity": "high"}).run()
    assert result.status == "pass"


def test_regex_fail():
    c = make_connector()
    c.run_query.return_value = pd.DataFrame({"val": ["not-an-email", "also-bad"], "cnt": [3, 1]})
    result = RegexCheck(c, {"table": "users", "column": "email", "pattern": r"^[^@]+@[^@]+\.[^@]+$", "severity": "high"}).run()
    assert result.status == "fail"
    assert "4 rows" in result.message


# ---------------------------------------------------------------------------
# RowCountCheck
# ---------------------------------------------------------------------------

def test_row_count_min_rows_pass():
    c = make_connector()
    c.run_query.return_value = pd.DataFrame({"row_count": [800]})
    result = RowCountCheck(c, {"table": "orders", "min_rows": 500, "severity": "high"}).run()
    assert result.status == "pass"


def test_row_count_min_rows_fail():
    c = make_connector()
    c.run_query.return_value = pd.DataFrame({"row_count": [300]})
    result = RowCountCheck(c, {"table": "orders", "min_rows": 500, "severity": "high"}).run()
    assert result.status == "fail"
    assert "minimum" in result.message


def test_row_count_delta_pass():
    c = make_connector()
    c.run_query.return_value = pd.DataFrame({"row_count": [820]})
    store = MagicMock()
    store.get_history.return_value = pd.DataFrame({"observed_value": ["800"]})
    result = RowCountCheck(c, {"table": "orders", "max_delta_pct": 0.20, "severity": "high"}, store=store).run()
    assert result.status == "pass"


def test_row_count_delta_fail():
    c = make_connector()
    c.run_query.return_value = pd.DataFrame({"row_count": [200]})
    store = MagicMock()
    store.get_history.return_value = pd.DataFrame({"observed_value": ["800"]})
    result = RowCountCheck(c, {"table": "orders", "max_delta_pct": 0.20, "severity": "high"}, store=store).run()
    assert result.status == "fail"


def test_row_count_self_calibrating_no_history():
    c = make_connector()
    c.run_query.return_value = pd.DataFrame({"row_count": [800]})
    store = MagicMock()
    store.get_history.return_value = pd.DataFrame()
    result = RowCountCheck(c, {"table": "orders", "severity": "high"}, store=store).run()
    assert result.status == "pass"
    assert "calibrating" in result.message


def test_row_count_self_calibrating_warn():
    c = make_connector()
    c.run_query.return_value = pd.DataFrame({"row_count": [400]})
    store = MagicMock()
    store.get_history.return_value = pd.DataFrame({"observed_value": ["800", "820", "810"]})
    result = RowCountCheck(c, {"table": "orders", "severity": "high"}, store=store).run()
    assert result.status == "warn"
    assert "7d avg" in result.message
