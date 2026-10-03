# Power BI dashboard

There are two ways to get the dashboard:

* **A. Open the ready-made project** (5 minutes): `powerbi/AI Customer Insights.pbip`
* **B. Build it yourself** (2–3 hours): the steps further down. Being able to explain the
  model and DAX is exactly what BI interviews test, so read the project even if you use A.

## A. Open the ready-made project

You need **Power BI Desktop** (free, Windows): Microsoft Store or
https://www.microsoft.com/power-platform/products/power-bi/desktop.

1. Download this repo (green **Code** button → *Download ZIP*, then unzip; or `git clone`).
2. Double-click **`powerbi/AI Customer Insights.pbip`**.
3. If Power BI asks how to connect to `raw.githubusercontent.com`, choose **Anonymous** → *Connect*.
   If it asks about privacy levels, choose **Public** (it's a public, open dataset).
4. Click **Refresh** (Home ribbon) if the visuals are empty. The first load takes about a minute,
   because it downloads ~23 MB of data from GitHub.
5. **File → Save as** → choose *Power BI file (.pbix)* if you also want a single `.pbix` file.

**Where the data comes from.** The model reads the 8 `powerbi/data/*.csv.gz` files. The
`DataFolder` parameter says where they are. By default that's this repo's branch on GitHub.
To change it: **Home → Transform data → Edit parameters**:

| You want to… | Set `DataFolder` to |
|---|---|
| Use the copy on GitHub's `main` branch (after this branch is merged) | `https://raw.githubusercontent.com/shobkro/ai-customer-insights/main/powerbi/data/` |
| Work offline from your own copy | your local folder, ending in `\`, e.g. `C:\Users\you\ai-customer-insights\powerbi\data\` |

After re-running the Python pipeline (`python run_all.py`), the `.csv.gz` files are rewritten.
Point `DataFolder` at your local folder and click **Refresh**.

**If Desktop says the format isn't supported:** update Power BI Desktop, or turn on
*File → Options → Preview features →* **Power BI Project (.pbip) save option**,
**Store semantic model using TMDL format** and **Store reports using enhanced metadata format (PBIR)**,
then restart Desktop.

### What's inside

| Part | Where | What |
|---|---|---|
| Model | `AI Customer Insights.SemanticModel/definition/` (TMDL text files) | 8 tables in a star schema, 7 relationships, `dim_date` marked as the date table, 24 DAX measures in `_Measures`, 3 calculated columns |
| Report | `AI Customer Insights.Report/definition/` (PBIR JSON) | 4 pages, 31 visuals, custom colour theme |
| Generator | `scripts/07_build_powerbi_project.py` | Writes both folders. Once you edit in Desktop, save from Desktop and don't re-run it (it overwrites). |

Model decisions worth explaining in an interview:
* `review_id` isn't unique in Olist, so reviews and AI labels join on `review_key = review_id|order_id` (built in Power Query).
* `fact_order_items → fact_orders` filters **both directions**, so product and seller slicers reach orders, reviews and AI labels. It's the only two-way relationship, so there are no ambiguous paths.
* `Customers` uses `CROSSFILTER` instead of a second two-way relationship.
* `Revenue 3M Rolling Avg` averages *monthly* totals, so it sits on the same scale as `Revenue`.
* Text and number types are set with the `en-US` culture in Power Query, so decimals load correctly whatever your Windows region is.

### The 4 pages

1. **Executive overview**: slicers (year, customer state, category), 5 KPI cards, monthly revenue with 3-month rolling average, late delivery % by state.
2. **Delivery and satisfaction**: score gap late vs on time, review score and 1–2★ share by *Lateness Bucket*, states ranked by late %.
3. **What customers say (AI)**: complaint topics, urgency donut, category × topic matrix, negative reviews with the AI's English summary next to the original Portuguese text, and a note on the measured accuracy.
4. **Seller watch-list**: sellers with 100+ delivered orders, lowest review score first.

### Check the numbers (no filters selected)

If you see these, the model is working:

| Measure | Expected |
|---|---|
| Revenue | R$ 13,221,498 |
| Delivered Orders | 96,478 |
| Avg Order Value | R$ 137.04 |
| Late Delivery % | 8.1% |
| Avg Review Score | 4.09 |
| Avg score on time / late / gap | 4.29 / 2.57 / 1.73 |
| Labelled Reviews · Negative Share (AI) · High Urgency | 2,149 · 34.5% · 472 |
| Sellers on the watch-list | 210 |

### Finishing touches to do in Desktop

The layout was written as code, so polish it by eye:
* Page 3 matrix: *Format → Cell elements → Background color* on for a heat-map.
* Resize or re-colour anything that looks cramped on your screen.
* Export each page as PNG into `docs/images/` and add them to the README (see step 6 below).

---

# B. Build it yourself

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
