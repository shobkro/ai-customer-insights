"""Step 2 - Clean the raw CSVs and load them into a SQLite star schema.

Why SQLite? It's free, needs no server, and the same SQL runs on PostgreSQL
with minor changes (see sql/README.md). Output: data/olist.db
"""
import sqlite3
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.config import RAW_DIR, DB_PATH, ROOT


def read(name: str) -> pd.DataFrame:
    return pd.read_csv(RAW_DIR / name)


def build_dim_date(dates: pd.Series) -> pd.DataFrame:
    days = pd.date_range(dates.min().normalize(), dates.max().normalize(), freq="D")
    return pd.DataFrame({
        "date_key": days.strftime("%Y-%m-%d"),
        "year": days.year,
        "quarter": days.quarter,
        "month": days.month,
        "month_name": days.strftime("%b"),
        "year_month": days.strftime("%Y-%m"),
        "weekday": days.strftime("%a"),
    })


def main() -> None:
    orders = read("olist_orders_dataset.csv")
    items = read("olist_order_items_dataset.csv")
    payments = read("olist_order_payments_dataset.csv")
    reviews = read("olist_order_reviews_dataset.csv")
    customers = read("olist_customers_dataset.csv")
    products = read("olist_products_dataset.csv")
    sellers = read("olist_sellers_dataset.csv")
    translation = read("product_category_name_translation.csv")

    # ---- Dimensions -------------------------------------------------------
    dim_customer = customers.rename(columns={
        "customer_city": "city", "customer_state": "state"
    })[["customer_id", "customer_unique_id", "city", "state"]]

    products = products.merge(translation, on="product_category_name", how="left")
    products["category"] = (
        products["product_category_name_english"]
        .fillna(products["product_category_name"])
        .fillna("unknown")
    )
    dim_product = products.rename(columns={
        "product_weight_g": "weight_g", "product_photos_qty": "photos_qty"
    })[["product_id", "category", "weight_g", "photos_qty"]]

    dim_seller = sellers.rename(columns={
        "seller_city": "city", "seller_state": "state"
    })[["seller_id", "city", "state"]]

    # ---- Orders fact (one row per order) ----------------------------------
    for col in ["order_purchase_timestamp", "order_delivered_customer_date",
                "order_estimated_delivery_date"]:
        orders[col] = pd.to_datetime(orders[col], errors="coerce")

    item_totals = items.groupby("order_id").agg(
        order_value=("price", "sum"), freight_value=("freight_value", "sum")
    )
    # Main payment method = the payment with the largest value
    main_payment = (
        payments.sort_values("payment_value", ascending=False)
        .drop_duplicates("order_id")
        .set_index("order_id")[["payment_type", "payment_installments"]]
        .rename(columns={"payment_installments": "installments"})
    )

    fact_orders = orders.join(item_totals, on="order_id").join(main_payment, on="order_id")
    purchase = fact_orders["order_purchase_timestamp"]
    delivered = fact_orders["order_delivered_customer_date"]
    estimated = fact_orders["order_estimated_delivery_date"]
    fact_orders["delivery_days"] = ((delivered - purchase).dt.total_seconds() / 86400).round(1)
    fact_orders["days_late"] = ((delivered - estimated).dt.total_seconds() / 86400).round(1)
    fact_orders["is_late"] = (delivered > estimated).astype(int).where(delivered.notna())
    fact_orders["purchase_date"] = purchase.dt.strftime("%Y-%m-%d")

    def ts(s: pd.Series) -> pd.Series:
        return s.dt.strftime("%Y-%m-%d %H:%M:%S")

    fact_orders = pd.DataFrame({
        "order_id": fact_orders["order_id"],
        "customer_id": fact_orders["customer_id"],
        "order_status": fact_orders["order_status"],
        "purchase_ts": ts(purchase),
        "purchase_date": fact_orders["purchase_date"],
        "delivered_ts": ts(delivered),
        "estimated_delivery_ts": ts(estimated),
        "delivery_days": fact_orders["delivery_days"],
        "days_late": fact_orders["days_late"],
        "is_late": fact_orders["is_late"],
        "order_value": fact_orders["order_value"].round(2),
        "freight_value": fact_orders["freight_value"].round(2),
        "payment_type": fact_orders["payment_type"],
        "installments": fact_orders["installments"],
    })

    fact_items = items[["order_id", "order_item_id", "product_id", "seller_id",
                        "price", "freight_value"]]

    # ---- Reviews fact ------------------------------------------------------
    reviews = reviews.drop_duplicates(["review_id", "order_id"])
    for col in ["review_comment_title", "review_comment_message"]:
        reviews[col] = reviews[col].astype("string").str.strip().replace("", pd.NA)
    fact_reviews = pd.DataFrame({
        "review_id": reviews["review_id"],
        "order_id": reviews["order_id"],
        "review_score": reviews["review_score"],
        "comment_title": reviews["review_comment_title"],
        "comment_message": reviews["review_comment_message"],
        "review_date": pd.to_datetime(reviews["review_creation_date"]).dt.strftime("%Y-%m-%d"),
    })

    dim_date = build_dim_date(purchase.dropna())

    # ---- Load --------------------------------------------------------------
    if DB_PATH.exists():
        DB_PATH.unlink()
    con = sqlite3.connect(DB_PATH)
    con.executescript((ROOT / "sql" / "01_schema.sql").read_text(encoding="utf-8"))
    for name, df in [("dim_customer", dim_customer), ("dim_product", dim_product),
                     ("dim_seller", dim_seller), ("dim_date", dim_date),
                     ("fact_orders", fact_orders), ("fact_order_items", fact_items),
                     ("fact_reviews", fact_reviews)]:
        df.to_sql(name, con, if_exists="append", index=False)
        print(f"{name:<18} {len(df):>8,} rows")
    con.commit()
    con.close()
    print(f"Database ready: {DB_PATH}")


if __name__ == "__main__":
    main()
