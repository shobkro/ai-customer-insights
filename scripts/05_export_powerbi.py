"""Step 5 - Export the star schema as CSVs for Power BI Desktop (free).

Output: powerbi/data/*.csv     ->  Power BI: Get Data > Text/CSV (manual build)
        powerbi/data/*.csv.gz  ->  read by the ready-made Power BI project
                                   (powerbi/AI Customer Insights.pbip), committed to git
See powerbi/BUILD_GUIDE.md for the model, DAX measures and page layout.
"""
import gzip
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
        # Whole-number columns with blanks come back as floats ("1.0"); keep them whole
        for col in ("is_late", "installments", "photos_qty"):
            if col in df:
                df[col] = df[col].astype("Int64")
        df.to_csv(POWERBI_DIR / f"{name}.csv", index=False, encoding="utf-8")
        # mtime=0 keeps the .gz byte-identical between runs (no noisy git diffs)
        with gzip.GzipFile(POWERBI_DIR / f"{name}.csv.gz", "wb", mtime=0) as gz:
            gz.write(df.to_csv(index=False).encode("utf-8"))
        print(f"{name:<18} {len(df):>8,} rows")
    con.close()
    print(f"CSV files ready in {POWERBI_DIR}")


if __name__ == "__main__":
    main()
