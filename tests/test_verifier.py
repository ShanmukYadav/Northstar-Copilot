"""Deterministic verifier regression tests — no API key required."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "verifier"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "sandbox"))

from checks import (
    VerificationResult,
    check_read_only,
    check_schema_grounded,
    check_join_grain,
    check_customer_key,
)


def test_rejects_write_sql():
    r = VerificationResult()
    assert check_read_only("DELETE FROM orders", r) is False
    assert r.status == "fail"


def test_accepts_select():
    r = VerificationResult()
    assert check_read_only("SELECT COUNT(*) FROM orders", r) is True


def test_join_grain_trap():
    r = VerificationResult()
    sql = "SELECT COUNT(order_id) FROM orders JOIN order_items USING (order_id)"
    assert check_join_grain(sql, r) is False


def test_join_grain_ok_with_distinct():
    r = VerificationResult()
    sql = "SELECT COUNT(DISTINCT order_id) FROM orders JOIN order_items USING (order_id)"
    assert check_join_grain(sql, r) is True


def test_customer_key_trap():
    r = VerificationResult()
    sql = "SELECT COUNT(DISTINCT customer_id) FROM customers"
    assert check_customer_key(sql, r) is False


def test_customer_key_ok():
    r = VerificationResult()
    sql = "SELECT COUNT(DISTINCT customer_unique_id) FROM customers"
    assert check_customer_key(sql, r) is True


def test_schema_grounded_rejects_invented_column():
    r = VerificationResult()
    sql = "SELECT invented_column_xyz FROM orders"
    assert check_schema_grounded(sql, r) is False
