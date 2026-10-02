import sqlite3

import pytest

from src.sql_guard import UnsafeSQLError, extract_sql, run_readonly, validate_sql


@pytest.mark.parametrize("sql", [
    "DELETE FROM fact_orders",
    "DROP TABLE fact_orders",
    "SELECT 1; DROP TABLE fact_orders",
    "UPDATE fact_orders SET order_value = 0",
    "PRAGMA table_info(fact_orders)",
    "ATTACH DATABASE 'x.db' AS x",
    "SELECT * FROM sqlite_master",
    "SELECT * FROM secret_table",
    "",
])
def test_blocks_unsafe(sql):
    with pytest.raises(UnsafeSQLError):
        validate_sql(sql)


def test_allows_select_and_adds_limit():
    out = validate_sql("SELECT state FROM dim_customer")
    assert out.strip().endswith("LIMIT 500")


def test_allows_cte_and_keeps_existing_limit():
    sql = "WITH t AS (SELECT * FROM fact_orders) SELECT COUNT(*) FROM t LIMIT 5"
    assert validate_sql(sql) == sql


def test_keyword_inside_string_is_fine():
    validate_sql("SELECT * FROM fact_reviews WHERE comment_message LIKE '%delete%'")


def test_extract_sql_from_fenced_reply():
    reply = "Here you go:\n```sql\nSELECT 1 AS x;\n```\nHope that helps"
    assert extract_sql(reply) == "SELECT 1 AS x"


def test_readonly_connection_cannot_write(tmp_path):
    db = tmp_path / "t.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE fact_orders (x INT)")
    con.commit()
    con.close()
    cols, rows = run_readonly(db, "SELECT COUNT(*) AS n FROM fact_orders")
    assert cols == ["n"] and rows == [(0,)]
    with pytest.raises(sqlite3.OperationalError):
        run_readonly(db, "INSERT INTO fact_orders VALUES (1)")  # guard bypassed -> DB still refuses
