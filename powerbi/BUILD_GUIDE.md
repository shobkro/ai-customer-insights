# Power BI build guide (Power BI Desktop is free on Windows)

Time: about 2–3 hours. Do this yourself. Being able to explain the model and DAX is
exactly what BI interviews test.

## 1. Get the data

```bash
python scripts/05_export_powerbi.py      # writes powerbi/data/*.csv
```

Power BI Desktop → **Get data → Text/CSV** → load all 8 files.

In **Power Query** (Transform data):
- `dim_date[date_key]` → change type to **Date** and rename it `Date`.
- `fact_orders[purchase_date]` → **Date**; `purchase_ts`, `delivered_ts`, `estimated_delivery_ts` → **Date/Time**.
- `fact_reviews[review_date]` → **Date**.
- Check that `is_late` is a **Whole number** and money columns are **Decimal**.

## 2. Model (star schema)

Model view → create these relationships (single direction, many-to-one):

| From (many) | To (one) |
|---|---|
| fact_orders[customer_id] | dim_customer[customer_id] |
| fact_orders[purchase_date] | dim_date[Date] |
| fact_order_items[order_id] | fact_orders[order_id] |
| fact_order_items[product_id] | dim_product[product_id] |
| fact_order_items[seller_id] | dim_seller[seller_id] |
| fact_reviews[order_id] | fact_orders[order_id] |
| review_ai_labels[review_id] | fact_reviews[review_id] * |

\* `review_id` isn't 100% unique in Olist (a few reviews cover two orders). Easiest fix: in Power Query
add a column `review_key = review_id & "|" & order_id` to **both** tables and relate on that.

Then: select `dim_date` → **Mark as date table** → `Date`. Hide the ID columns from report view.

## 3. Measures

Copy them from [`DAX_measures.md`](DAX_measures.md).

## 4. Report pages

**Page 1: Executive overview**
- Cards: Revenue, Delivered Orders, Avg Order Value, Late Delivery %, Avg Review Score
- Line: Revenue by `dim_date[year_month]` + Revenue 3M Rolling Avg
- Map or filled map: Late Delivery % by `dim_customer[state]`
- Slicers: year, state, category

**Page 2: Delivery → satisfaction (the main story)**
- Clustered column: Avg Review Score by lateness bucket. Add a calculated column on fact_orders:
  ```DAX
  Lateness Bucket =
  SWITCH ( TRUE (),
      ISBLANK ( fact_orders[days_late] ), "Not delivered",
      fact_orders[days_late] <= -7, "1. 7+ days early",
      fact_orders[days_late] <= 0, "2. 0-7 days early",
      fact_orders[days_late] <= 3, "3. 1-3 days late",
      fact_orders[days_late] <= 7, "4. 4-7 days late",
      "5. 8+ days late" )
  ```
- KPI card: Score Gap Late vs On Time
- Table: states with Late Delivery %, Avg Delivery Days, Avg Review Score (conditional formatting)

**Page 3: What customers say (AI)**
- Bar: Negative Reviews (AI) by `review_ai_labels[topic]`
- Matrix: `dim_product[category]` × topic, values = Negative Reviews (AI), heat-map formatting
- Donut: High/medium/low urgency
- Table: review_score, topic, urgency, summary_en, comment_message (drill-through target)
- Text box: "Labels produced by an LLM. Accuracy measured on 150 hand-labelled reviews: X%." (from `results/evaluation.md`)

**Page 4: Seller watch-list**
- Table: seller_id, Delivered Orders, Avg Review Score, Late Delivery %; filter to sellers with 100+ orders and sort by score ascending.

## 5. Optional: Copilot / Q&A
Power BI's free **Q&A visual** lets people type questions. Add synonyms in Modeling → Q&A setup
(e.g. "late" → `is_late`, "complaints" → `Negative Reviews (AI)`). Copilot itself needs paid Fabric capacity.

## 6. Publish to your portfolio (free)
"Publish to web" needs a paid licence, so instead:
- Save the `.pbix` into `powerbi/` and commit it (keep it under ~50 MB).
- Export each page as PNG (File → Export → PDF, or screenshots) into `docs/images/` and show them in the README.
- Record a 2-minute walkthrough video for LinkedIn.
