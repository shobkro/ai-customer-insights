"""Step 6 - Monthly KPI pack in Excel, with an AI-drafted executive summary.

    python scripts/06_excel_kpi_pack.py            # uses LLM_PROVIDER if available
    python scripts/06_excel_kpi_pack.py --no-ai    # data-driven template text instead

Output: excel/KPI_Pack.xlsx
 * KPI Summary - live formulas over the data sheets + a month selector (yellow cell)
 * Exec Summary - AI draft next to an 'Analyst final' column you edit:
                  shows you REVIEW AI output instead of pasting it blindly
 * Monthly / Categories / Complaints - data with formulas and a chart
"""
import argparse
import json
import sqlite3
import sys
from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.chart import BarChart, LineChart, Reference
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src import config
from src.config import DB_PATH, EXCEL_DIR
from src.llm import LLMError, ask_llm

FONT = "Arial"
HEADER_FILL = PatternFill("solid", start_color="1F3864")
INPUT_FILL = PatternFill("solid", start_color="FFFF00")
THIN = Side(style="thin", color="BFBFBF")
BORDER = Border(top=THIN, bottom=THIN, left=THIN, right=THIN)


def data(con) -> dict[str, pd.DataFrame]:
    monthly = pd.read_sql_query("""
        SELECT d.year_month AS month,
               COUNT(*) AS orders,
               ROUND(SUM(o.order_value), 2) AS revenue,
               SUM(o.is_late) AS late_orders,
               SUM(o.is_late IS NOT NULL) AS orders_with_delivery_date,
               COUNT(r.review_score) AS reviews,
               SUM(r.review_score) AS review_points
        FROM fact_orders o
        JOIN dim_date d ON d.date_key = o.purchase_date
        LEFT JOIN (SELECT order_id, AVG(review_score) review_score FROM fact_reviews GROUP BY order_id) r
               ON r.order_id = o.order_id
        WHERE o.order_status = 'delivered' AND d.year_month BETWEEN '2017-01' AND '2018-08'
        GROUP BY d.year_month ORDER BY d.year_month""", con)
    categories = pd.read_sql_query("""
        SELECT p.category, COUNT(DISTINCT i.order_id) AS orders, ROUND(SUM(i.price), 2) AS revenue,
               ROUND(AVG(r.review_score), 2) AS avg_score
        FROM fact_order_items i JOIN dim_product p ON p.product_id = i.product_id
        JOIN fact_orders o ON o.order_id = i.order_id
        LEFT JOIN fact_reviews r ON r.order_id = i.order_id
        WHERE o.order_status = 'delivered'
        GROUP BY p.category HAVING COUNT(DISTINCT i.order_id) >= 300
        ORDER BY revenue DESC""", con)
    complaints = pd.read_sql_query("""
        SELECT topic, COUNT(*) AS negative_reviews,
               SUM(urgency = 'high') AS high_urgency
        FROM review_ai_labels WHERE sentiment = 'negative'
        GROUP BY topic ORDER BY negative_reviews DESC""", con)
    provider = pd.read_sql_query("SELECT provider FROM review_ai_labels LIMIT 1", con)
    return {"monthly": monthly, "categories": categories, "complaints": complaints,
            "label_provider": provider.provider[0] if len(provider) else "none"}


def facts_for_summary(d) -> dict:
    m = d["monthly"]
    last, prev = m.iloc[-1], m.iloc[-2]
    total_late = m.late_orders.sum() / m.orders_with_delivery_date.sum()
    return {
        "period": f"{m.month.iloc[0]} to {m.month.iloc[-1]}",
        "total_orders": int(m.orders.sum()),
        "total_revenue_brl": round(float(m.revenue.sum())),
        "latest_month": last.month,
        "latest_month_revenue": round(float(last.revenue)),
        "mom_revenue_change_pct": round(100 * (last.revenue / prev.revenue - 1), 1),
        "late_delivery_rate_pct": round(100 * total_late, 1),
        "avg_review_score": round(float(m.review_points.sum() / m.reviews.sum()), 2),
        "top_category": d["categories"].category.iloc[0],
        "lowest_rated_big_category": d["categories"].sort_values("avg_score").category.iloc[0],
        "top_complaint_topics": d["complaints"].head(3)[["topic", "negative_reviews"]].to_dict("records"),
    }


def draft_summary(facts: dict, use_ai: bool) -> tuple[list[str], str]:
    if use_ai and config.LLM_PROVIDER != "rules":
        try:
            reply = ask_llm(
                "You write concise executive summaries for e-commerce managers. Use ONLY the "
                "numbers provided. Return JSON: {\"bullets\": [5 short bullet strings]}. "
                "Include one recommended action.",
                json.dumps(facts), json_mode=True)
            bullets = json.loads(reply)["bullets"][:6]
            return [str(b) for b in bullets], f"AI draft ({config.LLM_PROVIDER})"
        except (LLMError, ValueError, KeyError) as exc:
            print(f"AI summary unavailable ({exc}); using template text.")
    f = facts
    topics = ", ".join(t["topic"].replace("_", " ") for t in f["top_complaint_topics"])
    return [
        f"{f['total_orders']:,} delivered orders worth R$ {f['total_revenue_brl']:,} ({f['period']}).",
        f"{f['latest_month']} revenue was R$ {f['latest_month_revenue']:,}, "
        f"{f['mom_revenue_change_pct']:+.1f}% vs the previous month.",
        f"{f['late_delivery_rate_pct']}% of orders arrived late; average review score is {f['avg_review_score']} / 5.",
        f"Top revenue category: {f['top_category']}. Lowest-rated large category: {f['lowest_rated_big_category']}.",
        f"Most common complaint topics: {topics}.",
        "Recommended action: prioritise on-time delivery in the worst-performing states, "
        "since late orders score ~1.7 stars lower.",
    ], "Template draft (no AI available)"


def style_header(ws, row: int, ncols: int, start_col: int = 1):
    for c in range(start_col, start_col + ncols):
        cell = ws.cell(row=row, column=c)
        cell.font = Font(name=FONT, bold=True, color="FFFFFF")
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = BORDER


def write_table(ws, df: pd.DataFrame, start_row: int = 1, formats: dict | None = None):
    for j, col in enumerate(df.columns, 1):
        ws.cell(row=start_row, column=j, value=col)
    style_header(ws, start_row, len(df.columns))
    for i, row in enumerate(df.itertuples(index=False), start_row + 1):
        for j, val in enumerate(row, 1):
            cell = ws.cell(row=i, column=j, value=val.item() if hasattr(val, "item") else val)
            cell.font = Font(name=FONT)
            cell.border = BORDER
            fmt = (formats or {}).get(df.columns[j - 1])
            if fmt:
                cell.number_format = fmt
    return start_row + len(df)  # last row


def build(d, bullets: list[str], source: str) -> Workbook:
    wb = Workbook()

    # ---------------- Monthly (data + formula columns) ----------------
    ws_m = wb.active
    ws_m.title = "Monthly"
    m = d["monthly"]
    last = write_table(ws_m, m, formats={"revenue": "#,##0", "orders": "#,##0"})
    extra = ["AOV (BRL)", "Late %", "Avg score", "Revenue MoM %"]
    for k, name in enumerate(extra, 8):
        ws_m.cell(row=1, column=k, value=name)
    style_header(ws_m, 1, len(extra), start_col=8)
    for r in range(2, last + 1):
        ws_m[f"H{r}"] = f"=IFERROR(C{r}/B{r},0)"
        ws_m[f"I{r}"] = f"=IFERROR(D{r}/E{r},0)"
        ws_m[f"J{r}"] = f"=IFERROR(G{r}/F{r},0)"
        ws_m[f"K{r}"] = "-" if r == 2 else f"=IFERROR(C{r}/C{r - 1}-1,0)"
        for col, fmt in zip("HIJK", ["#,##0.00", "0.0%", "0.00", "0.0%;(0.0%);-"]):
            ws_m[f"{col}{r}"].number_format = fmt
            ws_m[f"{col}{r}"].font = Font(name=FONT)
            ws_m[f"{col}{r}"].border = BORDER
    chart = LineChart()
    chart.title = "Monthly revenue (BRL)"
    chart.height, chart.width = 8, 18
    chart.add_data(Reference(ws_m, min_col=3, min_row=1, max_row=last), titles_from_data=True)
    chart.set_categories(Reference(ws_m, min_col=1, min_row=2, max_row=last))
    chart.legend = None
    ws_m.add_chart(chart, "M2")

    # ---------------- Categories ----------------
    ws_c = wb.create_sheet("Categories")
    cat = d["categories"]
    last_c = write_table(ws_c, cat, formats={"revenue": "#,##0", "orders": "#,##0"})
    for k, name in enumerate(["Revenue share", "Revenue rank"], 5):
        ws_c.cell(row=1, column=k, value=name)
    style_header(ws_c, 1, 2, start_col=5)
    for r in range(2, last_c + 1):
        ws_c[f"E{r}"] = f"=C{r}/SUM($C$2:$C${last_c})"
        ws_c[f"E{r}"].number_format = "0.0%"
        ws_c[f"F{r}"] = f"=RANK(C{r},$C$2:$C${last_c})"
        for col in "EF":
            ws_c[f"{col}{r}"].font = Font(name=FONT)
            ws_c[f"{col}{r}"].border = BORDER

    # ---------------- Complaints ----------------
    ws_t = wb.create_sheet("Complaints")
    comp = d["complaints"]
    last_t = write_table(ws_t, comp)
    ws_t.cell(row=1, column=4, value="Share of complaints")
    style_header(ws_t, 1, 1, start_col=4)
    for r in range(2, last_t + 1):
        ws_t[f"D{r}"] = f"=B{r}/SUM($B$2:$B${last_t})"
        ws_t[f"D{r}"].number_format = "0.0%"
        ws_t[f"D{r}"].font = Font(name=FONT)
    ws_t.cell(row=last_t + 2, column=1,
              value=f"Source: AI labels of review text, provider = {d['label_provider']} "
                    "(see results/evaluation.md for measured accuracy).").font = Font(name=FONT, italic=True)
    bar = BarChart()
    bar.type = "bar"
    bar.title = "Complaint topics"
    bar.height, bar.width = 8, 16
    bar.add_data(Reference(ws_t, min_col=2, min_row=1, max_row=last_t), titles_from_data=True)
    bar.set_categories(Reference(ws_t, min_col=1, min_row=2, max_row=last_t))
    bar.legend = None
    ws_t.add_chart(bar, "F2")

    # ---------------- KPI Summary (first sheet) ----------------
    ws = wb.create_sheet("KPI Summary", 0)
    ws["A1"] = "E-commerce KPI Pack"
    ws["A1"].font = Font(name=FONT, bold=True, size=16, color="1F3864")
    ws["A2"] = "Olist marketplace · delivered orders · values in BRL"
    ws["A2"].font = Font(name=FONT, italic=True, color="808080")

    ws["A4"], ws["B4"] = "Select month:", m.month.iloc[-1]
    ws["B4"].fill = INPUT_FILL
    ws["B4"].font = Font(name=FONT, bold=True, color="0000FF")
    ws["B4"].comment = Comment("Input: pick any month from the list (yellow = editable).", "KPI Pack")
    dv = DataValidation(type="list", formula1=f"=Monthly!$A$2:$A${last}", allow_blank=False)
    ws.add_data_validation(dv)
    dv.add("B4")

    rng = lambda col: f"Monthly!${col}$2:${col}${last}"  # noqa: E731
    look = lambda col: f"INDEX({rng(col)},MATCH($B$4,{rng('A')},0))"  # noqa: E731
    rows = [
        ("KPI", "Selected month", "Previous month", "Change", "All months"),
        ("Orders", f"={look('B')}", f"=IFERROR(INDEX({rng('B')},MATCH($B$4,{rng('A')},0)-1),0)", None, f"=SUM({rng('B')})"),
        ("Revenue (BRL)", f"={look('C')}", f"=IFERROR(INDEX({rng('C')},MATCH($B$4,{rng('A')},0)-1),0)", None, f"=SUM({rng('C')})"),
        ("Avg order value (BRL)", "=IFERROR(C8/C7,0)", "=IFERROR(D8/D7,0)", None, "=IFERROR(F8/F7,0)"),
        ("Late delivery %", f"=IFERROR({look('D')}/{look('E')},0)",
         f"=IFERROR(INDEX({rng('D')},MATCH($B$4,{rng('A')},0)-1)/INDEX({rng('E')},MATCH($B$4,{rng('A')},0)-1),0)",
         None, f"=SUM({rng('D')})/SUM({rng('E')})"),
        ("Avg review score", f"=IFERROR({look('G')}/{look('F')},0)",
         f"=IFERROR(INDEX({rng('G')},MATCH($B$4,{rng('A')},0)-1)/INDEX({rng('F')},MATCH($B$4,{rng('A')},0)-1),0)",
         None, f"=SUM({rng('G')})/SUM({rng('F')})"),
    ]
    fmts = {7: "#,##0", 8: "#,##0", 9: "#,##0.00", 10: "0.0%", 11: "0.00"}
    for i, row in enumerate(rows, 6):
        for j, val in enumerate(row, 2):
            if val is not None:
                ws.cell(row=i, column=j, value=val)
        if i == 6:
            style_header(ws, 6, 5, start_col=2)
            continue
        ws.cell(row=i, column=5, value=f"=IFERROR(C{i}/D{i}-1,0)" if i not in (10, 11) else f"=C{i}-D{i}")
        for j in range(2, 7):
            cell = ws.cell(row=i, column=j)
            cell.font = Font(name=FONT, bold=(j == 2))
            cell.border = BORDER
            if j in (3, 4, 6):
                cell.number_format = fmts[i]
        ws.cell(row=i, column=5).number_format = (
            "+0.0%;-0.0%;-" if i not in (10, 11) else ("+0.0%;-0.0%;-" if i == 10 else "+0.00;-0.00;-"))
    ws["B13"] = "Note: the first month has no previous month, so its comparison columns show 0."
    ws["B13"].font = Font(name=FONT, italic=True, color="808080", size=9)

    # ---------------- Exec Summary ----------------
    ws_e = wb.create_sheet("Exec Summary", 1)
    ws_e["A1"] = "Executive summary"
    ws_e["A1"].font = Font(name=FONT, bold=True, size=16, color="1F3864")
    ws_e["A2"] = ("Workflow: AI writes a first draft from the numbers -> analyst checks every figure "
                  "against 'KPI Summary' and edits the yellow column -> only the analyst column is sent.")
    ws_e["A2"].font = Font(name=FONT, italic=True, color="808080")
    for j, h in enumerate([f"{source}", "Analyst final (edit me)", "Checked? (Y/N)"], 1):
        ws_e.cell(row=4, column=j, value=h)
    style_header(ws_e, 4, 3)
    for i, b in enumerate(bullets, 5):
        ws_e.cell(row=i, column=1, value=b)
        ws_e.cell(row=i, column=2, value=b).fill = INPUT_FILL
        ws_e.cell(row=i, column=3, value="N").fill = INPUT_FILL
        for j in (1, 2, 3):
            c = ws_e.cell(row=i, column=j)
            c.font = Font(name=FONT, color="0000FF" if j > 1 else "000000")
            c.alignment = Alignment(wrap_text=True, vertical="top")
            c.border = BORDER
    n = len(bullets)
    ws_e.cell(row=5 + n + 1, column=1, value="Bullets checked:")
    ws_e.cell(row=5 + n + 1, column=2, value=f'=COUNTIF(C5:C{4 + n},"Y")&" of {n}"')
    for c in (1, 2):
        ws_e.cell(row=5 + n + 1, column=c).font = Font(name=FONT, bold=True)

    # widths
    for sheet, widths in [(ws, [3, 24, 16, 16, 12, 16]), (ws_e, [70, 70, 14]),
                          (ws_m, [10, 9, 12, 11, 14, 9, 13, 12, 9, 10, 13]),
                          (ws_c, [28, 10, 14, 11, 14, 13]), (ws_t, [26, 16, 13, 18])]:
        for k, w in enumerate(widths, 1):
            sheet.column_dimensions[get_column_letter(k)].width = w
    for sheet in (ws_m, ws_c, ws_t):
        sheet.freeze_panes = "A2"
    return wb


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-ai", action="store_true")
    args = ap.parse_args()
    con = sqlite3.connect(DB_PATH)
    d = data(con)
    con.close()
    bullets, source = draft_summary(facts_for_summary(d), use_ai=not args.no_ai)
    out = EXCEL_DIR / "KPI_Pack.xlsx"
    build(d, bullets, source).save(out)
    print(f"Saved {out}  ({source})")


if __name__ == "__main__":
    main()
