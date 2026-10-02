# SQL

- `01_schema.sql`: star schema (facts + dimensions + `review_ai_labels`)
- `02_analysis_queries.sql`: 10 business questions; run them all with `python scripts/run_sql_analysis.py`

## Running on PostgreSQL instead of SQLite
The queries are standard SQL. Changes needed:
- `AVG(condition)` → `AVG(CASE WHEN condition THEN 1 ELSE 0 END)` (SQLite treats booleans as 0/1)
- Store `purchase_ts` etc. as `TIMESTAMP` and `purchase_date` as `DATE`
- `ROUND(x, 1)` on a double → `ROUND(x::numeric, 1)`
