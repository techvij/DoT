"""Tests for connector dialect helpers and BigQuery table resolution — no live DB required."""
import pytest

from dot.connectors.base import BaseConnector
from dot.connectors.bigquery import BigQueryConnector


class _ConcreteConnector(BaseConnector):
    def connect(self): pass
    def run_query(self, sql): pass


# --- BaseConnector (Postgres defaults) ---

def test_base_cast_float():
    c = _ConcreteConnector()
    assert c.cast_float("amount") == "CAST(amount AS FLOAT)"


def test_base_cast_string():
    c = _ConcreteConnector()
    assert c.cast_string("status") == "status::TEXT"


def test_base_regex_match():
    c = _ConcreteConnector()
    assert c.regex_match("code", r"^EMP-\d+$") == r"code ~ '^EMP-\d+$'"


def test_base_resolve_table_passthrough():
    c = _ConcreteConnector()
    assert c.resolve_table("orders") == "orders"


# --- BigQueryConnector table resolution ---

@pytest.fixture
def bq():
    return BigQueryConnector({"project": "my-project", "dataset": "my_dataset"})


def test_bq_one_part_table(bq):
    assert bq.resolve_table("orders") == "`my-project.my_dataset.orders`"


def test_bq_two_part_table(bq):
    assert bq.resolve_table("other_ds.orders") == "`my-project.other_ds.orders`"


def test_bq_three_part_table(bq):
    assert bq.resolve_table("other-project.other_ds.orders") == "`other-project.other_ds.orders`"


def test_bq_one_part_no_dataset_raises():
    conn = BigQueryConnector({"project": "p"})
    with pytest.raises(ValueError, match="no default 'dataset'"):
        conn.resolve_table("orders")


def test_bq_cast_float(bq):
    assert bq.cast_float("amount") == "CAST(amount AS FLOAT64)"


def test_bq_cast_string(bq):
    assert bq.cast_string("status") == "CAST(status AS STRING)"


def test_bq_regex_match(bq):
    assert bq.regex_match("code", r"^EMP-\d+$") == r"REGEXP_CONTAINS(code, r'^EMP-\d+$')"
