"""Guardrails for AI-generated SQL.

An LLM can write SQL that is wrong, slow, or destructive. Before anything
runs we check it, and then we run it on a READ-ONLY connection anyway
(defence in depth: two independent layers).
"""
from __future__ import annotations

import re
import sqlite3
import time
from pathlib import Path

ALLOWED_TABLES = {
    "fact_orders", "fact_order_items", "fact_reviews", "review_ai_labels",
    "dim_customer", "dim_product", "dim_seller", "dim_date",
}
FORBIDDEN = r"\b(insert|update|delete|drop|alter|create|replace|attach|detach|pragma|vacuum|reindex|truncate|grant)\b"
MAX_ROWS = 500


class UnsafeSQLError(ValueError):
    pass


def extract_sql(text: str) -> str:
    """Pull SQL out of an LLM reply (handles ```sql fences and chatter)."""
    fenced = re.search(r"```(?:sql)?\s*(.*?)```", text, flags=re.S | re.I)
    sql = fenced.group(1) if fenced else text
    match = re.search(r"\b(with|select)\b.*", sql, flags=re.S | re.I)
    return (match.group(0) if match else sql).strip().rstrip(";").strip()


def _strip_strings_and_comments(sql: str) -> str:
    sql = re.sub(r"'(?:[^']|'')*'", "''", sql)          # string literals
    sql = re.sub(r"--[^\n]*", " ", sql)                  # line comments
    return re.sub(r"/\*.*?\*/", " ", sql, flags=re.S)    # block comments


def validate_sql(sql: str) -> str:
    """Return a safe version of `sql` or raise UnsafeSQLError explaining why."""
    if not sql.strip():
        raise UnsafeSQLError("Empty query.")
    code = _strip_strings_and_comments(sql).lower()
    if ";" in code:
        raise UnsafeSQLError("Only one statement is allowed.")
    if not re.match(r"^\s*(select|with)\b", code):
        raise UnsafeSQLError("Only SELECT queries are allowed.")
    bad = re.search(FORBIDDEN, code)
    if bad:
        raise UnsafeSQLError(f"Forbidden keyword: {bad.group(1).upper()}")

    cte_names = set(re.findall(r"(?:with|,)\s*([a-z_][a-z0-9_]*)\s+as\s*\(", code))
    tables = set(re.findall(r"\b(?:from|join)\s+([a-z_][a-z0-9_]*)", code))
    unknown = tables - ALLOWED_TABLES - cte_names
    if unknown:
        raise UnsafeSQLError(f"Unknown or not allowed table(s): {', '.join(sorted(unknown))}")

    if not re.search(r"\blimit\s+\d+\s*$", code.strip()):
        sql = f"{sql.rstrip()}\nLIMIT {MAX_ROWS}"
    return sql


def run_readonly(db_path: Path, sql: str, timeout_s: float = 10.0):
    """Execute on a read-only connection with a time limit. Returns (columns, rows)."""
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    deadline = time.time() + timeout_s
    con.set_progress_handler(lambda: 1 if time.time() > deadline else 0, 10_000)
    try:
        cur = con.execute(sql)
        cols = [d[0] for d in cur.description]
        return cols, cur.fetchmany(MAX_ROWS)
    except sqlite3.OperationalError as exc:
        if "interrupted" in str(exc):
            raise UnsafeSQLError(f"Query took longer than {timeout_s}s and was stopped.") from exc
        raise
    finally:
        con.close()
