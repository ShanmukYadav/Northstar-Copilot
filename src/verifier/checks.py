"""
Deterministic Verifier checks - the rule-based first pass described in
docs/stage3_design/architecture.md section 5 ("Deterministic rules first; LLM only for
judgment-call checks"). This is real, runnable logic, not a design description.

Matches the check names in docs/stage3_design/agent_contracts.json verifier_output.checks_run.
"""
import sys
import os
import re
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "sandbox"))
from build_db import get_readonly_connection

IDENTIFIER_ALLOWLIST = {
    "orders", "order_items", "order_payments", "order_reviews", "products",
    "customers", "sellers", "category_translation",
    "order_id", "customer_id", "customer_unique_id", "order_status",
    "order_purchase_timestamp", "order_delivered_customer_date",
    "order_delivered_carrier_date", "order_estimated_delivery_date", "order_approved_at",
    "product_id", "product_category_name", "product_category_name_english",
    "seller_id", "price", "freight_value", "payment_value", "payment_type",
    "payment_installments", "review_score", "review_id", "review_comment_title",
    "review_comment_message", "review_creation_date", "review_answer_timestamp",
    "customer_state", "customer_city", "seller_state", "seller_city", "order_item_id",
    "shipping_limit_date", "customer_zip_code_prefix", "seller_zip_code_prefix",
}

SQL_FUNCTIONS = {
    "date_trunc", "date_diff", "date_part", "extract", "cast", "coalesce",
    "strftime", "epoch", "round", "abs", "min", "max", "now", "current_date",
}

# Date-part keywords valid inside EXTRACT(... FROM ...) / DATE_PART(...) - these are
# SQL syntax, not schema identifiers. Missing this was a real bug found via live
# Query Writer testing (Sprint 2): EXTRACT(YEAR FROM order_purchase_timestamp) was
# being false-flagged as an ungrounded identifier because 'year' wasn't recognized.
# Third bug of this class found (after alias handling, string literals) - regex-based
# identifier extraction keeps missing real SQL vocabulary; the original design doc
# (agent_contract_result_verifier.md) called for AST-based parsing (sqlglot) instead
# of regex heuristics for exactly this reason. This fix patches the immediate bug;
# migrating to a real SQL parser is the more durable fix, still open.
DATE_PART_KEYWORDS = {
    "year", "month", "day", "hour", "minute", "second", "quarter", "week",
    "dow", "doy", "epoch", "date", "time", "timestamp",
}


class VerificationResult:
    def __init__(self):
        self.status = "pass"
        self.checks_run = []
        self.failure_reason = None
        self.row_count = None
        self.execution_error = None

    def fail(self, check, reason):
        self.status = "fail"
        self.failure_reason = reason
        if check not in self.checks_run:
            self.checks_run.append(check)

    def to_dict(self):
        return {
            "status": self.status,
            "checks_run": self.checks_run,
            "failure_reason": self.failure_reason,
            "row_count": self.row_count,
        }


def check_read_only(sql: str, result: VerificationResult):
    """Reject anything that isn't a pure SELECT. Real enforcement, not a prompt request."""
    forbidden = re.compile(r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|ATTACH|COPY)\b", re.I)
    if forbidden.search(sql):
        result.fail("read_only_enforced", f"Query contains a forbidden write/DDL keyword: {sql}")
        return False
    if not sql.strip().upper().startswith("SELECT") and not sql.strip().upper().startswith("WITH"):
        result.fail("read_only_enforced", "Query must start with SELECT or WITH")
        return False
    result.checks_run.append("read_only_enforced")
    return True


def check_schema_grounded(sql: str, result: VerificationResult):
    """
    Every identifier the query touches must resolve against the real allowlist -
    catches risk register risk #4 (hallucinated schema/metric).

    Must exclude AS-aliases (e.g. COUNT(...) AS order_count) - an alias is a name
    the query itself defines, not a schema reference, so flagging it as "ungrounded"
    is a false positive. This distinction was missing in the first version of this
    check and was caught by the Sprint 1 spike, not by review - exactly what a spike
    is for.
    """
    # Strip string literals BEFORE extracting identifiers - 'delivered', 'day', etc.
    # are literal values, not column/table references, and were the harness's second
    # real bug find (false positives on every query with a WHERE ... = 'x' clause).
    sql_no_literals = re.sub(r"'[^']*'", "", sql)

    # Column/table aliases: AS <name> or <expr> AS <name> - capture the alias name
    aliases = set(re.findall(r"\bas\s+([a-z_][a-z0-9_]*)\b", sql_no_literals.lower()))
    # Table aliases used as prefixes (e.g. "orders o", "order_items oi") - capture the
    # short alias tokens so "o.order_id" doesn't flag "o" as an ungrounded identifier
    table_aliases = set(re.findall(r"\b(?:from|join)\s+[a-z_][a-z0-9_]*\s+([a-z][a-z0-9_]{0,3})\b", sql_no_literals.lower()))

    identifiers = set(re.findall(r"\b([a-z_][a-z0-9_]*)\b", sql_no_literals.lower()))
    sql_keywords = {"select", "from", "where", "join", "on", "and", "or", "group", "by",
                     "order", "having", "as", "count", "sum", "avg", "distinct", "left",
                     "inner", "right", "outer", "not", "null", "in", "is", "desc", "asc",
                     "limit", "with", "case", "when", "then", "else", "end", "between"}
    candidate_identifiers = identifiers - sql_keywords - aliases - table_aliases - SQL_FUNCTIONS - DATE_PART_KEYWORDS
    unknown = {i for i in candidate_identifiers if i not in IDENTIFIER_ALLOWLIST
               and not i.isdigit() and len(i) > 2}
    if unknown:
        result.fail("schema_grounded", f"Ungrounded identifiers not in schema allowlist: {unknown}")
        return False
    result.checks_run.append("schema_grounded")
    return True


def check_join_grain(sql: str, result: VerificationResult):
    """
    Canonical adversarial case (risk #6): joining orders to order_items and doing
    COUNT(order_id) instead of COUNT(DISTINCT order_id) overcounts, since 9.9% of
    real orders have >1 item.
    """
    sql_lower = sql.lower()
    joins_items = "order_items" in sql_lower
    counts_order_id = re.search(r"count\s*\(\s*order_id\s*\)", sql_lower)
    counts_distinct_order_id = re.search(r"count\s*\(\s*distinct\s+order_id\s*\)", sql_lower)
    if joins_items and counts_order_id and not counts_distinct_order_id:
        result.fail("join_grain_correct",
                     "Query joins order_items and does COUNT(order_id) without DISTINCT - "
                     "will overcount orders with multiple line items (9.9% of real orders)")
        return False
    result.checks_run.append("join_grain_correct")
    return True


def check_customer_key(sql: str, result: VerificationResult):
    """
    Canonical adversarial case (risk #7): counting distinct customer_id when the
    question means unique customers double-counts, since Olist issues a new
    customer_id per order (99,441 customer_id vs 96,096 customer_unique_id).
    """
    sql_lower = sql.lower()
    asks_unique_customers = ("distinct customer_id" in sql_lower
                              and "customer_unique_id" not in sql_lower)
    if asks_unique_customers:
        result.fail("customer_key_correct",
                     "Query uses COUNT(DISTINCT customer_id) - this counts order-level IDs, "
                     "not real unique customers (customer_unique_id). "
                     "customer_id != customer (Olist issues one per order).")
        return False
    result.checks_run.append("customer_key_correct")
    return True


def check_row_count_sane(row_count: int, result: VerificationResult):
    if row_count == 0:
        result.fail("row_count_sane", "Query returned zero rows - likely wrong filter or join")
        return False
    if row_count > 50000:
        result.fail("row_count_sane", f"Query returned {row_count} rows - likely missing an aggregation")
        return False
    result.checks_run.append("row_count_sane")
    return True


def verify(sql: str) -> VerificationResult:
    """
    Full verification pipeline: run every deterministic check, execute the query
    against the REAL sandboxed data only if the static checks pass, then check the
    result shape too. This is the actual Verifier agent's logic, runnable end to end.
    """
    result = VerificationResult()

    if not check_read_only(sql, result):
        return result
    if not check_schema_grounded(sql, result):
        return result
    if not check_join_grain(sql, result):
        return result
    if not check_customer_key(sql, result):
        return result

    con = get_readonly_connection()
    try:
        rows = con.execute(sql).fetchall()
        result.row_count = len(rows)
    except Exception as e:
        result.execution_error = str(e)
        result.fail("executes_successfully", f"SQL execution failed: {e}")
        return result
    finally:
        con.close()

    check_row_count_sane(result.row_count, result)
    return result
