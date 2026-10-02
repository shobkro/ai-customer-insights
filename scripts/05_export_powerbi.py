"""Step 5 - Export the star schema as CSVs for Power BI Desktop (free).

Output: powerbi/data/*.csv  ->  Power BI: Get Data > Text/CSV (or Folder)
See powerbi/BUILD_GUIDE.md for the model, DAX measures and page layout.
"""
import sqlite3
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.config import DB_PATH, POWERBI_DIR

TABLES = {
    "fact_orders": "SELECT * FROM fact_orders",
    "fact_order_items": "SELECT * FROM fact_order_items",
    # Review text is long; Power BI only needs it for the drill-through table
    "fact_reviews": "SELECT review_id, order_id, review_score, review_date, "
                    "substr(comment_message, 1, 300) AS comment_message FROM fact_reviews",
    "review_ai_labels": "SELECT * FROM review_ai_labels",
    "dim_customer": "SELECT * FROM dim_customer",
    "dim_product": "SELECT * FROM dim_product",
    "dim_seller": "SELECT * FROM dim_seller",
    "dim_date": "SELECT * FROM dim_date",
}


def main() -> None:
    con = sqlite3.connect(DB_PATH)
    for name, sql in TABLES.items():
        df = pd.read_sql_query(sql, con)
        df.to_csv(POWERBI_DIR / f"{name}.csv", index=False, encoding="utf-8")
        print(f"{name:<18} {len(df):>8,} rows")
    con.close()
    print(f"CSV files ready in {POWERBI_DIR}")


if __name__ == "__main__":
    main()
