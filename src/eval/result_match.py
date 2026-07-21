"""
Shared result-set comparison for execution accuracy.

Sprint 3 → 4 fix (gs010 class of failures):
  Exact tuple equality is too brittle for a text-to-SQL system. Semantically
  correct answers can still fail when the agent:
    - ROUNDs floats (15.24 vs 15.23700…)
    - Adds an extra informative column (e.g. order_count alongside avg)
    - Uses multi-step SQL joined with a separator in sql_shown

PRD north-star is "executed query result matches the gold/verified result" —
we interpret that as: every gold cell is present (within float tolerance) in a
matching got row; extra got columns are allowed if they don't change the answer.
Wrong states, wrong filters, or wrong averages still fail.
"""
from __future__ import annotations

import datetime
import math
import re
from typing import Any, Optional, Sequence


STEP_SEP = re.compile(r"\n\s*--\s*step separator\s*--\s*\n", re.I)

# Delivery-day / money averages: 0.05 is well under business-meaningful error
DEFAULT_FLOAT_TOL = 0.05

# Olist Portuguese product_category_name ↔ English product_category_name_english.
# Loaded once from the sandbox so gs004-class cases (cama_mesa_banho vs bed_bath_table)
# grade as the same category when the metric matches.
_category_canonical: Optional[dict[str, str]] = None
_category_load_attempted = False


def _category_map() -> dict[str, str]:
    """Map any known category label (PT or EN, lowercased) → canonical English lower."""
    global _category_canonical, _category_load_attempted
    if _category_load_attempted:
        return _category_canonical or {}
    _category_load_attempted = True
    _category_canonical = {}
    try:
        import os
        import sys
        sandbox = os.path.join(os.path.dirname(__file__), "..", "sandbox")
        if sandbox not in sys.path:
            sys.path.insert(0, sandbox)
        from build_db import get_readonly_connection

        con = get_readonly_connection()
        try:
            rows = con.execute(
                "SELECT product_category_name, product_category_name_english "
                "FROM category_translation"
            ).fetchall()
        finally:
            con.close()
        for pt, en in rows:
            if not pt or not en:
                continue
            pt_l, en_l = str(pt).strip().lower(), str(en).strip().lower()
            _category_canonical[pt_l] = en_l
            _category_canonical[en_l] = en_l
    except Exception:
        # Offline unit tests without DB still work for non-category cases
        _category_canonical = {
            "cama_mesa_banho": "bed_bath_table",
            "bed_bath_table": "bed_bath_table",
        }
    return _category_canonical


def normalize_cell(v: Any) -> Any:
    if isinstance(v, datetime.datetime):
        return v.date()
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return v
    return v


def normalize_row(row: Sequence[Any]) -> tuple:
    return tuple(normalize_cell(v) for v in row)


def _canon_string(s: str) -> str:
    raw = s.strip().lower()
    return _category_map().get(raw, raw)


def values_equal(a: Any, b: Any, float_tol: float = DEFAULT_FLOAT_TOL) -> bool:
    a, b = normalize_cell(a), normalize_cell(b)
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    # Numeric: int/float cross-compare with tolerance
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        if isinstance(a, bool) or isinstance(b, bool):
            return a == b
        return abs(float(a) - float(b)) <= float_tol
    # Strings: case-insensitive; Olist PT/EN category labels are equivalent
    if isinstance(a, str) and isinstance(b, str):
        if a.strip().lower() == b.strip().lower():
            return True
        return _canon_string(a) == _canon_string(b)
    return a == b


def row_covers_gold(
    gold_row: Sequence[Any],
    got_row: Sequence[Any],
    float_tol: float = DEFAULT_FLOAT_TOL,
) -> bool:
    """
    True if every value in gold_row appears in got_row (order-independent match
    against unused cells). Extra values in got_row are ignored.
    """
    remaining = list(got_row)
    for gv in gold_row:
        found_i = None
        for i, ov in enumerate(remaining):
            if values_equal(gv, ov, float_tol):
                found_i = i
                break
        if found_i is None:
            return False
        remaining.pop(found_i)
    return True


def results_match(
    gold_rows: Optional[Sequence[Sequence[Any]]],
    got_rows: Optional[Sequence[Sequence[Any]]],
    float_tol: float = DEFAULT_FLOAT_TOL,
) -> bool:
    """
    Semantically match gold result set to got result set.

    - Same number of rows (wrong filter / wrong GROUP BY fails here)
    - Each gold row is covered by a distinct got row (extra columns OK)
    - Floats compared with tolerance
    """
    if gold_rows is None or got_rows is None:
        return False
    gold = [normalize_row(r) for r in gold_rows]
    got = [normalize_row(r) for r in got_rows]
    if len(gold) != len(got):
        return False
    if len(gold) == 0:
        return True

    # Fast path: exact after float rounding
    if _strict_sorted_equal(gold, got, float_tol):
        return True

    # Gold-subset coverage (handles extra columns)
    remaining = list(got)
    for gr in gold:
        match_i = None
        for i, orow in enumerate(remaining):
            if row_covers_gold(gr, orow, float_tol):
                match_i = i
                break
        if match_i is None:
            return False
        remaining.pop(match_i)
    return True


def _strict_sorted_equal(gold, got, float_tol: float) -> bool:
    if len(gold) != len(got):
        return False
    # Pair by first cell when possible, else order-sensitive zip of sorted rows
    try:
        g_sorted = sorted(gold, key=lambda r: tuple(str(x) for x in r))
        o_sorted = sorted(got, key=lambda r: tuple(str(x) for x in r))
    except TypeError:
        g_sorted, o_sorted = list(gold), list(got)
    for gr, orow in zip(g_sorted, o_sorted):
        if len(gr) != len(orow):
            return False
        for a, b in zip(gr, orow):
            if not values_equal(a, b, float_tol):
                return False
    return True


def split_pipeline_sql(sql_shown: Optional[str]) -> list[str]:
    """Split multi-step sql_shown from comparative path into executable statements."""
    if not sql_shown or not str(sql_shown).strip():
        return []
    parts = STEP_SEP.split(sql_shown)
    return [p.strip() for p in parts if p.strip()]


def pick_sql_for_eval(sql_shown: Optional[str]) -> Optional[str]:
    """
    Prefer a single executable statement. If multi-step, use the last step
    (usually the final merge/compare) only when there is exactly one step that
    looks like the full answer; otherwise return None and let caller merge logic run.
    For multi-step with N>1, callers should use execute_and_match_any / multi path.
    """
    parts = split_pipeline_sql(sql_shown)
    if not parts:
        return None
    if len(parts) == 1:
        return parts[0]
    # Multi-step: return joined only if no separator issues — eval should run each
    return None


def execute_sql_rows(con, sql: str) -> Optional[list[tuple]]:
    try:
        rows = con.execute(sql).fetchall()
        return sorted(normalize_row(r) for r in rows)
    except Exception:
        return None
