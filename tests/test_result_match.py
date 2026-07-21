"""Unit tests for semantic result matching (gs010-class fixes). No API key."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "eval"))

from result_match import (
    results_match,
    values_equal,
    split_pipeline_sql,
    row_covers_gold,
)


def test_gs010_rounded_extra_column_passes():
    """The exact failure mode from the Sprint 3 eval run."""
    gold = [("RJ", 15.237004048582996), ("SP", 8.70057292438386)]
    got = [("RJ", 15.24, 12350), ("SP", 8.7, 40494)]
    assert results_match(gold, got) is True


def test_wrong_average_still_fails():
    gold = [("RJ", 15.237), ("SP", 8.700)]
    got = [("RJ", 20.0), ("SP", 8.700)]
    assert results_match(gold, got) is False


def test_wrong_state_fails():
    gold = [("RJ", 15.237), ("SP", 8.700)]
    got = [("MG", 15.237), ("SP", 8.700)]
    assert results_match(gold, got) is False


def test_row_count_mismatch_fails():
    gold = [("RJ", 15.0), ("SP", 8.0)]
    got = [("SP", 8.0)]
    assert results_match(gold, got) is False


def test_exact_match_still_works():
    gold = [(96096,)]
    got = [(96096,)]
    assert results_match(gold, got) is True


def test_float_tolerance():
    assert values_equal(15.237, 15.24, float_tol=0.05) is True
    assert values_equal(15.237, 16.0, float_tol=0.05) is False


def test_split_multi_step_sql():
    sql = "SELECT 1 AS a\n-- step separator --\nSELECT 2 AS b"
    parts = split_pipeline_sql(sql)
    assert len(parts) == 2
    assert "SELECT 1" in parts[0]
    assert "SELECT 2" in parts[1]


def test_row_covers_ignores_extra_cols():
    assert row_covers_gold(("SP", 8.7), ("SP", 8.70, 9999)) is True


def test_gs004_portuguese_vs_english_category_passes():
    """Same top category + count; gold uses EN, agent used PT raw name."""
    gold = [("bed_bath_table", 11115)]
    got = [("cama_mesa_banho", 11115)]
    assert results_match(gold, got) is True


def test_wrong_category_still_fails():
    gold = [("bed_bath_table", 11115)]
    got = [("sports_leisure", 11115)]
    assert results_match(gold, got) is False
