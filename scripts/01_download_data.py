"""Step 1 - Download the Olist Brazilian E-commerce dataset (free, public).

Source: Olist's official public copy on GitHub (same data as the Kaggle dataset
"Brazilian E-Commerce Public Dataset by Olist"). ~100k orders, 2016-2018.
"""
import sys
from pathlib import Path
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.config import RAW_DIR

BASE = "https://raw.githubusercontent.com/olist/work-at-olist-data/master/datasets"
FILES = [
    "olist_customers_dataset.csv",
    "olist_order_items_dataset.csv",
    "olist_order_payments_dataset.csv",
    "olist_order_reviews_dataset.csv",
    "olist_orders_dataset.csv",
    "olist_products_dataset.csv",
    "olist_sellers_dataset.csv",
    "product_category_name_translation.csv",
]


def main() -> None:
    for name in FILES:
        target = RAW_DIR / name
        if target.exists():
            print(f"already have {name}")
            continue
        print(f"downloading {name} ...")
        resp = requests.get(f"{BASE}/{name}", timeout=120)
        resp.raise_for_status()
        target.write_bytes(resp.content)
    print(f"Done. Files are in {RAW_DIR}")


if __name__ == "__main__":
    main()
