"""Step 7 - Write the ready-made Power BI project (PBIP) for the dashboard.

    python scripts/07_build_powerbi_project.py

Output: powerbi/AI Customer Insights.pbip  (open it in Power BI Desktop)
        powerbi/AI Customer Insights.SemanticModel/   model as TMDL: tables, relationships, DAX
        powerbi/AI Customer Insights.Report/          4 report pages as PBIR JSON

The model reads powerbi/data/*.csv.gz (written by 05_export_powerbi.py). By default it
downloads them from this public GitHub repo, so nothing has to be installed; point the
DataFolder parameter at a local folder to work offline (see powerbi/BUILD_GUIDE.md).

Re-running this overwrites the project folders. Once you start editing the report in
Power BI Desktop, save from Desktop and stop re-running this script.
"""
import json
import shutil
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.config import ROOT

NAME = "AI Customer Insights"
OUT = ROOT / "powerbi"
MODEL_DIR = OUT / f"{NAME}.SemanticModel"
REPORT_DIR = OUT / f"{NAME}.Report"
DEFAULT_DATA_FOLDER = (
    "https://raw.githubusercontent.com/shobkro/ai-customer-insights/"
    "claude/ai-project-power-bi-zxrtnv/powerbi/data/"
)
SCHEMA = "https://developer.microsoft.com/json-schemas/fabric"


def stable_id(*parts: str) -> str:
    """Deterministic ids, so re-running the script gives a clean git diff."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "ai-customer-insights/" + "/".join(parts)))


def short_id(*parts: str) -> str:
    return stable_id(*parts).replace("-", "")[:20]


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def write_json(path: Path, data: dict) -> None:
    write(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def quote(name: str) -> str:
    """TMDL object names with spaces or symbols go in single quotes."""
    return name if name.replace("_", "").isalnum() else "'" + name.replace("'", "''") + "'"


# =============================================================================
# Semantic model
# =============================================================================
# (csv column, TMDL dataType, M type, extra TMDL properties)
TEXT, INT, NUM, DATE, DATETIME = "string", "int64", "double", "date", "datetime"
M_TYPES = {TEXT: "type text", INT: "Int64.Type", NUM: "type number",
           DATE: "type date", DATETIME: "type datetime"}
TMDL_TYPES = {TEXT: "string", INT: "int64", NUM: "double", DATE: "dateTime", DATETIME: "dateTime"}

TABLES = {
    "fact_orders": [
        ("order_id", TEXT, {"isHidden": True}),
        ("customer_id", TEXT, {"isHidden": True}),
        ("order_status", TEXT, {}),
        ("purchase_ts", DATETIME, {"formatString": "General Date"}),
        ("purchase_date", DATE, {"formatString": "Short Date"}),
        ("delivered_ts", DATETIME, {"formatString": "General Date"}),
        ("estimated_delivery_ts", DATETIME, {"formatString": "General Date"}),
        ("delivery_days", NUM, {"formatString": "0.0", "summarizeBy": "average"}),
        ("days_late", NUM, {"formatString": "0.0", "summarizeBy": "average"}),
        ("is_late", INT, {"formatString": "0"}),
        ("order_value", NUM, {"formatString": '"R$ "#,0.00', "summarizeBy": "sum"}),
        ("freight_value", NUM, {"formatString": '"R$ "#,0.00', "summarizeBy": "sum"}),
        ("payment_type", TEXT, {}),
        ("installments", INT, {"formatString": "0"}),
    ],
    "fact_order_items": [
        ("order_id", TEXT, {"isHidden": True}),
        ("order_item_id", INT, {"isHidden": True, "formatString": "0"}),
        ("product_id", TEXT, {"isHidden": True}),
        ("seller_id", TEXT, {"isHidden": True}),
        ("price", NUM, {"formatString": '"R$ "#,0.00', "summarizeBy": "sum"}),
        ("freight_value", NUM, {"formatString": '"R$ "#,0.00', "summarizeBy": "sum"}),
    ],
    "fact_reviews": [
        ("review_id", TEXT, {"isHidden": True}),
        ("order_id", TEXT, {"isHidden": True}),
        ("review_score", INT, {"formatString": "0", "summarizeBy": "average"}),
        ("review_date", DATE, {"formatString": "Short Date"}),
        ("comment_message", TEXT, {}),
    ],
    "review_ai_labels": [
        ("review_id", TEXT, {"isHidden": True}),
        ("order_id", TEXT, {"isHidden": True}),
        ("sentiment", TEXT, {}),
        ("topic", TEXT, {}),
        ("urgency", TEXT, {}),
        ("summary_en", TEXT, {}),
        ("provider", TEXT, {}),
    ],
    "dim_customer": [
        ("customer_id", TEXT, {"isHidden": True}),
        ("customer_unique_id", TEXT, {"isHidden": True}),
        ("city", TEXT, {"dataCategory": "City"}),
        ("state", TEXT, {"dataCategory": "StateOrProvince"}),
    ],
    "dim_product": [
        ("product_id", TEXT, {"isHidden": True}),
        ("category", TEXT, {}),
        ("weight_g", NUM, {"formatString": "#,0", "summarizeBy": "average"}),
        ("photos_qty", INT, {"formatString": "0", "summarizeBy": "average"}),
    ],
    "dim_seller": [
        ("seller_id", TEXT, {}),
        ("city", TEXT, {"dataCategory": "City"}),
        ("state", TEXT, {"dataCategory": "StateOrProvince"}),
    ],
    "dim_date": [
        ("Date", DATE, {"formatString": "Short Date", "isKey": True}),
        ("year", INT, {"formatString": "0"}),
        ("quarter", INT, {"formatString": "0"}),
        ("month", INT, {"formatString": "0", "isHidden": True}),
        ("month_name", TEXT, {"sortByColumn": "month"}),
        ("year_month", TEXT, {}),
        ("weekday", TEXT, {}),
    ],
}

# Calculated columns: (table, name, DAX, TMDL dataType)
CALC_COLUMNS = [
    ("fact_orders", "Lateness Bucket", """
SWITCH (
    TRUE (),
    ISBLANK ( fact_orders[days_late] ), "Not delivered",
    fact_orders[days_late] <= -7, "1. 7+ days early",
    fact_orders[days_late] <= 0, "2. 0-7 days early",
    fact_orders[days_late] <= 3, "3. 1-3 days late",
    fact_orders[days_late] <= 7, "4. 4-7 days late",
    "5. 8+ days late"
)""", "string"),
    ("review_ai_labels", "Stars", "RELATED ( fact_reviews[review_score] )", "int64"),
    ("review_ai_labels", "Review text", "RELATED ( fact_reviews[comment_message] )", "string"),
]

# (name, DAX, formatString, display folder)
BRL = '"R$ "#,0'
MEASURES = [
    # Core sales
    ("Orders", "COUNTROWS ( fact_orders )", "#,0", "Sales"),
    ("Delivered Orders", 'CALCULATE ( COUNTROWS ( fact_orders ), fact_orders[order_status] = "delivered" )',
     "#,0", "Sales"),
    ("Revenue", 'CALCULATE ( SUM ( fact_orders[order_value] ), fact_orders[order_status] = "delivered" )',
     BRL, "Sales"),
    ("Avg Order Value", "DIVIDE ( [Revenue], [Delivered Orders] )", '"R$ "#,0.00', "Sales"),
    # dim_customer sits on the "one" side, so the order filter has to be pushed back to it
    ("Customers", """
CALCULATE (
    DISTINCTCOUNT ( dim_customer[customer_unique_id] ),
    fact_orders[order_status] = "delivered",
    CROSSFILTER ( fact_orders[customer_id], dim_customer[customer_id], BOTH )
)""", "#,0", "Sales"),
    # Time intelligence (dim_date is marked as the date table)
    ("Revenue PM", "CALCULATE ( [Revenue], DATEADD ( dim_date[Date], -1, MONTH ) )", BRL, "Time"),
    ("Revenue MoM %", "DIVIDE ( [Revenue] - [Revenue PM], [Revenue PM] )", "0.0%", "Time"),
    ("Revenue YTD", "TOTALYTD ( [Revenue], dim_date[Date] )", BRL, "Time"),
    # Average of the monthly totals (not of daily revenue), so it sits on the same scale as Revenue
    ("Revenue 3M Rolling Avg", """
VAR LastDate = MAX ( dim_date[Date] )
VAR Months =
    CALCULATETABLE (
        VALUES ( dim_date[year_month] ),
        DATESINPERIOD ( dim_date[Date], LastDate, -3, MONTH )
    )
RETURN
    AVERAGEX ( Months, CALCULATE ( [Revenue] ) )""", BRL, "Time"),
    # Delivery & satisfaction
    ("Late Orders", "CALCULATE ( COUNTROWS ( fact_orders ), fact_orders[is_late] = 1 )", "#,0", "Delivery"),
    ("Late Delivery %", """
DIVIDE (
    [Late Orders],
    CALCULATE ( COUNTROWS ( fact_orders ), NOT ISBLANK ( fact_orders[is_late] ) )
)""", "0.0%", "Delivery"),
    ("Avg Delivery Days",
     'CALCULATE ( AVERAGE ( fact_orders[delivery_days] ), fact_orders[order_status] = "delivered" )',
     "0.0", "Delivery"),
    ("Reviews", "COUNTROWS ( fact_reviews )", "#,0", "Satisfaction"),
    ("Avg Review Score", "AVERAGE ( fact_reviews[review_score] )", "0.00", "Satisfaction"),
    ("% 1-2 Star Reviews", """
DIVIDE (
    CALCULATE ( COUNTROWS ( fact_reviews ), fact_reviews[review_score] <= 2 ),
    COUNTROWS ( fact_reviews )
)""", "0.0%", "Satisfaction"),
    ("Avg Score On Time", "CALCULATE ( [Avg Review Score], fact_orders[is_late] = 0 )", "0.00", "Satisfaction"),
    ("Avg Score Late", "CALCULATE ( [Avg Review Score], fact_orders[is_late] = 1 )", "0.00", "Satisfaction"),
    ("Score Gap Late vs On Time", "[Avg Score On Time] - [Avg Score Late]", "0.00", "Satisfaction"),
    # AI review labels
    ("Labelled Reviews", "COUNTROWS ( review_ai_labels )", "#,0", "AI labels"),
    ("Negative Reviews (AI)",
     'CALCULATE ( COUNTROWS ( review_ai_labels ), review_ai_labels[sentiment] = "negative" )',
     "#,0", "AI labels"),
    ("Negative Share (AI)", "DIVIDE ( [Negative Reviews (AI)], [Labelled Reviews] )", "0.0%", "AI labels"),
    ("High Urgency Reviews",
     'CALCULATE ( COUNTROWS ( review_ai_labels ), review_ai_labels[urgency] = "high" )',
     "#,0", "AI labels"),
    ("Topic Share of Complaints", """
DIVIDE (
    [Negative Reviews (AI)],
    CALCULATE ( [Negative Reviews (AI)], ALL ( review_ai_labels[topic] ) )
)""", "0.0%", "AI labels"),
    # Titles
    ("Overview Title", """
"Revenue " & FORMAT ( [Revenue], "R$ #,0" ) & "  ·  Late deliveries "
    & FORMAT ( [Late Delivery %], "0.0%" ) & "  ·  Avg review "
    & FORMAT ( [Avg Review Score], "0.00" ) & "★\"""", None, "Titles"),
]

RELATIONSHIPS = [
    # (from table, from column, to table, to column, both directions?)
    ("fact_orders", "customer_id", "dim_customer", "customer_id", False),
    ("fact_orders", "purchase_date", "dim_date", "Date", False),
    # Both directions so product / seller slicers reach orders, reviews and AI labels
    ("fact_order_items", "order_id", "fact_orders", "order_id", True),
    ("fact_order_items", "product_id", "dim_product", "product_id", False),
    ("fact_order_items", "seller_id", "dim_seller", "seller_id", False),
    ("fact_reviews", "order_id", "fact_orders", "order_id", False),
    # review_id alone isn't unique in Olist, so relate on review_id|order_id
    ("review_ai_labels", "review_key", "fact_reviews", "review_key", False),
]


def tmdl_props(props: dict, indent: str) -> str:
    lines = []
    for key, value in props.items():
        if value is True:
            lines.append(f"{indent}{key}")
        elif key == "formatString" and '"' in value:
            lines.append(f'{indent}{key}: "{value.replace(chr(34), chr(34) * 2)}"')
        elif key == "sortByColumn":
            lines.append(f"{indent}{key}: {quote(value)}")
        else:
            lines.append(f"{indent}{key}: {value}")
    return "\n".join(lines)


def dax_block(expr: str, indent: str) -> str:
    """Single-line DAX stays on the header line; multi-line DAX goes indented below it."""
    expr = expr.strip("\n")
    if "\n" not in expr:
        return " " + expr
    return "\n" + "\n".join(indent + line if line else "" for line in expr.split("\n"))


def m_partition(table: str, columns: list) -> str:
    csv_name = f"{table}.csv.gz"
    renames = {"dim_date": '\n    Renamed = Table.RenameColumns(Promoted, {{"date_key", "Date"}}),'}
    source_step = "Renamed" if table in renames else "Promoted"
    types = ",\n            ".join(f'{{"{c}", {M_TYPES[t]}}}' for c, t, _ in columns)
    key_step = ""
    last = "Typed"
    if table in ("fact_reviews", "review_ai_labels"):
        key_step = ('\n    WithKey = Table.AddColumn(Typed, "review_key", '
                    'each [review_id] & "|" & [order_id], type text),')
        last = "WithKey"
    m = f"""let
    Raw = if Text.StartsWith(DataFolder, "http")
        then Web.Contents(DataFolder & "{csv_name}")
        else File.Contents(DataFolder & "{csv_name}"),
    Parsed = Csv.Document(
        Binary.Decompress(Raw, Compression.GZip),
        [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]
    ),
    Promoted = Table.PromoteHeaders(Parsed, [PromoteAllScalars = true]),{renames.get(table, "")}
    Typed = Table.TransformColumnTypes(
        {source_step},
        {{
            {types}
        }},
        "en-US"
    ),{key_step}
    Result = {last}
in
    Result"""
    body = "\n".join("\t\t\t\t" + line for line in m.split("\n"))
    return f"\tpartition {table} = m\n\t\tmode: import\n\t\tsource =\n{body}\n"


def table_tmdl(table: str, columns: list) -> str:
    out = [f"table {table}\n"]
    if table == "dim_date":
        out[0] = f"table {table}\n\tdataCategory: Time\n"
    for col, typ, extra in columns:
        props = {"dataType": TMDL_TYPES[typ]}
        props.update({k: v for k, v in extra.items() if k != "summarizeBy"})
        props["summarizeBy"] = extra.get("summarizeBy", "none")
        props["sourceColumn"] = col
        out.append(f"\tcolumn {quote(col)}\n{tmdl_props(props, chr(9) * 2)}\n")
    if table in ("fact_reviews", "review_ai_labels"):
        out.append("\tcolumn review_key\n\t\tdataType: string\n\t\tisHidden\n"
                   "\t\tsummarizeBy: none\n\t\tsourceColumn: review_key\n")
    for t, name, dax, typ in CALC_COLUMNS:
        if t == table:
            out.append(f"\tcolumn {quote(name)} ={dax_block(dax, chr(9) * 3)}\n"
                       f"\t\tdataType: {typ}\n\t\tsummarizeBy: none\n")
    out.append(m_partition(table, columns))
    return "\n".join(out)


def measures_tmdl() -> str:
    out = ["table _Measures\n"]
    for name, dax, fmt, folder in MEASURES:
        props = {}
        if fmt:
            props["formatString"] = fmt
        props["displayFolder"] = folder
        out.append(f"\tmeasure {quote(name)} ={dax_block(dax, chr(9) * 3)}\n"
                   f"{tmdl_props(props, chr(9) * 2)}\n")
    # A measure-only table still needs one (hidden) column and a partition
    out.append("\tcolumn Placeholder\n\t\tdataType: int64\n\t\tisHidden\n\t\tformatString: 0\n"
               "\t\tsummarizeBy: none\n\t\tsourceColumn: Placeholder\n")
    out.append("\tpartition _Measures = m\n\t\tmode: import\n\t\tsource =\n"
               "\t\t\t\tlet\n\t\t\t\t    Source = #table(type table [Placeholder = Int64.Type], {})\n"
               "\t\t\t\tin\n\t\t\t\t    Source\n")
    return "\n".join(out)


def build_model() -> None:
    d = MODEL_DIR / "definition"
    write_json(MODEL_DIR / "definition.pbism", {
        "$schema": f"{SCHEMA}/item/semanticModel/definitionProperties/1.0.0/schema.json",
        "version": "4.2",
        "settings": {"qnaEnabled": True},
    })
    write_json(MODEL_DIR / ".platform", {
        "$schema": f"{SCHEMA}/gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {"type": "SemanticModel", "displayName": NAME},
        "config": {"version": "2.0", "logicalId": stable_id("model")},
    })
    write(d / "database.tmdl", "database\n\tcompatibilityLevel: 1601\n")
    refs = "\n".join(f"ref table {t}" for t in ["_Measures", *TABLES])
    write(d / "model.tmdl", f"""model Model
\tculture: en-US
\tdefaultPowerBIDataSourceVersion: powerBI_V3
\tdiscourageImplicitMeasures
\tsourceQueryCulture: en-US
\tdataAccessOptions
\t\tlegacyRedirects
\t\treturnErrorValuesAsNull

annotation PBI_QueryOrder = {json.dumps(["DataFolder", "_Measures", *TABLES])}

{refs}
""")
    write(d / "expressions.tmdl",
          f'/// Where the .csv.gz files are: a URL ending in "/" or a local folder ending in "\\"\n'
          f'expression DataFolder = "{DEFAULT_DATA_FOLDER}" '
          'meta [IsParameterQuery = true, Type = "Text", IsParameterQueryRequired = true]\n')
    rel = []
    for ft, fc, tt, tc, both in RELATIONSHIPS:
        lines = [f"relationship {stable_id('rel', ft, fc, tt)}"]
        if both:
            lines.append("\tcrossFilteringBehavior: bothDirections")
        lines += [f"\tfromColumn: {ft}.{quote(fc)}", f"\ttoColumn: {tt}.{quote(tc)}"]
        rel.append("\n".join(lines))
    write(d / "relationships.tmdl", "\n\n".join(rel) + "\n")
    write(d / "tables" / "_Measures.tmdl", measures_tmdl())
    for table, columns in TABLES.items():
        write(d / "tables" / f"{table}.tmdl", table_tmdl(table, columns))


# =============================================================================
# Report (PBIR)
# =============================================================================
def lit(value) -> dict:
    return {"expr": {"Literal": {"Value": value}}}


def col(table: str, column: str) -> dict:
    return {"Column": {"Expression": {"SourceRef": {"Entity": table}}, "Property": column}}


def measure(name: str) -> dict:
    return {"Measure": {"Expression": {"SourceRef": {"Entity": "_Measures"}}, "Property": name}}


def projection(field: dict) -> dict:
    kind = "Measure" if "Measure" in field else "Column"
    entity = field[kind]["Expression"]["SourceRef"]["Entity"]
    prop = field[kind]["Property"]
    p = {"field": field, "queryRef": f"{entity}.{prop}", "nativeQueryRef": prop}
    if kind == "Column":
        p["active"] = True
    return p


def M(name: str) -> dict:
    return measure(name)


def C(ref: str) -> dict:
    table, column = ref.split(".", 1)
    return col(table, column)


def container_objects(title: str | None) -> dict:
    objs = {
        "border": [{"properties": {"show": lit("true"), "radius": lit("8D"),
                                   "color": {"solid": {"color": lit("'#E1E4E8'")}}}}],
        "dropShadow": [{"properties": {"show": lit("false")}}],
    }
    if title:
        objs["title"] = [{"properties": {"show": lit("true"), "text": lit(f"'{title}'"),
                                         "fontSize": lit("12D"), "bold": lit("true")}}]
    else:
        objs["title"] = [{"properties": {"show": lit("false")}}]
    return objs


class Page:
    def __init__(self, key: str, display_name: str):
        self.key = key
        self.name = short_id("page", key)
        self.display_name = display_name
        self.visuals = []

    def add(self, key, visual_type, x, y, w, h, query=None, sort=None, objects=None,
            title=None, filters=None, container=None):
        visual = {"visualType": visual_type}
        if query:
            visual["query"] = {"queryState": {
                role: {"projections": [projection(f) for f in fields]}
                for role, fields in query.items()
            }}
            if sort:
                visual["query"]["sortDefinition"] = {"sort": [
                    {"field": f, "direction": d} for f, d in sort]}
        if objects:
            visual["objects"] = objects
        visual["visualContainerObjects"] = container or container_objects(title)
        visual["drillFilterOtherVisuals"] = True
        z = len(self.visuals) * 1000
        v = {
            "$schema": f"{SCHEMA}/item/report/definition/visualContainer/2.0.0/schema.json",
            "name": short_id("visual", self.key, key),
            "position": {"x": x, "y": y, "z": z, "width": w, "height": h, "tabOrder": z},
            "visual": visual,
        }
        if filters:
            v["filterConfig"] = {"filters": filters}
        self.visuals.append(v)

    # -- building blocks ------------------------------------------------------
    def header(self, text: str, subtitle: str):
        self.add("header", "textbox", 24, 12, 1232, 64, objects={"general": [{"properties": {
            "paragraphs": [
                {"textRuns": [{"value": text, "textStyle": {
                    "fontFamily": "Segoe UI Semibold", "fontSize": "20pt", "color": "#1F2937"}}]},
                {"textRuns": [{"value": subtitle, "textStyle": {
                    "fontFamily": "Segoe UI", "fontSize": "10pt", "color": "#6B7280"}}]},
            ]}}]}, container={"background": [{"properties": {"show": lit("false")}}]})

    def note(self, key, x, y, w, h, text: str):
        self.add(key, "textbox", x, y, w, h, objects={"general": [{"properties": {
            "paragraphs": [{"textRuns": [{"value": text, "textStyle": {
                "fontFamily": "Segoe UI", "fontSize": "9pt", "color": "#4B5563"}}]}]}}]},
            container={"background": [{"properties": {"show": lit("true"),
                                                      "color": {"solid": {"color": lit("'#F3F4F6'")}}}}],
                       "border": [{"properties": {"show": lit("false")}}]})

    def card(self, key, x, y, w, h, measure_name: str, label: str | None = None):
        objects = {
            "labels": [{"properties": {"fontSize": lit("22D"),
                                       "color": {"solid": {"color": lit("'#1F4E79'")}}}}],
            "categoryLabels": [{"properties": {"show": lit("true"), "fontSize": lit("10D")}}],
        }
        field = projection(M(measure_name))
        if label:
            field["displayName"] = label
        self.add(key, "card", x, y, w, h, query={"Values": [M(measure_name)]}, objects=objects)
        self.visuals[-1]["visual"]["query"]["queryState"]["Values"]["projections"][0] = field

    def slicer(self, key, x, y, w, h, field: dict, title: str):
        self.add(key, "slicer", x, y, w, h, query={"Values": [field]},
                 sort=[(field, "Ascending")],
                 objects={"data": [{"properties": {"mode": lit("'Dropdown'")}}]},
                 container=container_objects(None))
        # The slicer header shows the field's display name
        self.visuals[-1]["visual"]["query"]["queryState"]["Values"]["projections"][0]["displayName"] = title

    def json(self) -> dict:
        return {
            "$schema": f"{SCHEMA}/item/report/definition/page/1.4.0/schema.json",
            "name": self.name,
            "displayName": self.display_name,
            "displayOption": "FitToPage",
            "height": 720,
            "width": 1280,
            "objects": {"background": [{"properties": {
                "color": {"solid": {"color": lit("'#F7F8FA'")}}, "transparency": lit("0D")}}]},
        }


def in_filter(name: str, field: dict, values: list[str]) -> dict:
    table = field["Column"]["Expression"]["SourceRef"]["Entity"]
    prop = field["Column"]["Property"]
    return {
        "name": name,
        "field": field,
        "type": "Categorical",
        "filter": {
            "Version": 2,
            "From": [{"Name": "t", "Entity": table, "Type": 0}],
            "Where": [{"Condition": {"In": {
                "Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "t"}},
                                            "Property": prop}}],
                "Values": [[{"Literal": {"Value": f"'{v}'"}}] for v in values],
            }}}],
        },
    }


def at_least_filter(name: str, measure_name: str, minimum: int) -> dict:
    return {
        "name": name,
        "field": M(measure_name),
        "type": "Advanced",
        "filter": {
            "Version": 2,
            "From": [{"Name": "m", "Entity": "_Measures", "Type": 0}],
            "Where": [{"Condition": {"Comparison": {
                "ComparisonKind": 2,  # greater than or equal
                "Left": {"Measure": {"Expression": {"SourceRef": {"Source": "m"}},
                                     "Property": measure_name}},
                "Right": {"Literal": {"Value": f"{minimum}L"}},
            }}}],
        },
    }


def data_labels(fmt_show=True) -> dict:
    return {"labels": [{"properties": {"show": lit("true" if fmt_show else "false")}}]}


def build_pages() -> list[Page]:
    pages = []

    # ---- Page 1: Executive overview -----------------------------------------
    p = Page("overview", "Executive overview")
    p.header("Executive overview",
             "Olist marketplace, 2016-2018 · delivered orders only · use the slicers to filter every visual")
    p.slicer("s_year", 24, 84, 200, 56, C("dim_date.year"), "Year")
    p.slicer("s_state", 236, 84, 200, 56, C("dim_customer.state"), "Customer state")
    p.slicer("s_cat", 448, 84, 260, 56, C("dim_product.category"), "Product category")
    cards = [("Revenue", None), ("Delivered Orders", None), ("Avg Order Value", None),
             ("Late Delivery %", None), ("Avg Review Score", None)]
    for i, (m_name, label) in enumerate(cards):
        p.card(f"c{i}", 24 + i * 248, 152, 236, 100, m_name, label)
    p.add("line", "lineChart", 24, 264, 760, 440,
          query={"Category": [C("dim_date.year_month")],
                 "Y": [M("Revenue"), M("Revenue 3M Rolling Avg")]},
          sort=[(C("dim_date.year_month"), "Ascending")],
          title="Monthly revenue and 3-month rolling average")
    p.add("late_state", "clusteredBarChart", 796, 264, 460, 440,
          query={"Category": [C("dim_customer.state")], "Y": [M("Late Delivery %")]},
          sort=[(M("Late Delivery %"), "Descending")],
          objects=data_labels(), title="Late delivery % by customer state")
    pages.append(p)

    # ---- Page 2: Delivery -> satisfaction ------------------------------------
    p = Page("delivery", "Delivery and satisfaction")
    p.header("Late delivery is the biggest driver of bad reviews",
             "Review score by how early or late the order arrived compared with the promised date")
    p.card("c_gap", 24, 84, 300, 100, "Score Gap Late vs On Time", "Score gap: on time vs late")
    p.card("c_on", 336, 84, 300, 100, "Avg Score On Time", "Avg score, on time")
    p.card("c_late", 648, 84, 300, 100, "Avg Score Late", "Avg score, late")
    p.card("c_pct", 960, 84, 296, 100, "Late Delivery %")
    bucket = C("fact_orders.Lateness Bucket")
    p.add("score_bucket", "clusteredColumnChart", 24, 196, 616, 252,
          query={"Category": [bucket], "Y": [M("Avg Review Score")]},
          sort=[(bucket, "Ascending")], objects=data_labels(),
          title="Average review score by lateness")
    p.add("bad_bucket", "clusteredColumnChart", 652, 196, 604, 252,
          query={"Category": [bucket], "Y": [M("% 1-2 Star Reviews")]},
          sort=[(bucket, "Ascending")], objects=data_labels(),
          title="Share of 1-2 star reviews by lateness")
    p.add("state_table", "tableEx", 24, 460, 1232, 244,
          query={"Values": [C("dim_customer.state"), M("Delivered Orders"), M("Late Delivery %"),
                            M("Avg Delivery Days"), M("Avg Review Score")]},
          sort=[(M("Late Delivery %"), "Descending")],
          title="States ranked by late delivery %")
    pages.append(p)

    # ---- Page 3: What customers say (AI) -------------------------------------
    p = Page("ai", "What customers say (AI)")
    p.header("What customers say: AI-labelled reviews",
             "A local LLM read each Portuguese review and tagged its sentiment, topic and urgency")
    p.card("c_lab", 24, 84, 236, 100, "Labelled Reviews")
    p.card("c_neg", 272, 84, 236, 100, "Negative Share (AI)")
    p.card("c_high", 520, 84, 236, 100, "High Urgency Reviews")
    p.note("accuracy", 768, 84, 488, 100,
           "How far to trust these labels: checked against 150 reviews labelled by hand, the LLM "
           "(Ollama, local and free) got sentiment right 84.7% of the time and the complaint topic "
           "73.3% (keyword baseline: 54.7%). Good for trends and prioritising; not for decisions "
           "about individual customers. Details: results/evaluation.md")
    topic = C("review_ai_labels.topic")
    p.add("topics", "clusteredBarChart", 24, 196, 500, 260,
          query={"Category": [topic], "Y": [M("Negative Reviews (AI)")]},
          sort=[(M("Negative Reviews (AI)"), "Descending")], objects=data_labels(),
          title="What negative reviews are about")
    p.add("urgency", "donutChart", 536, 196, 300, 260,
          query={"Category": [C("review_ai_labels.urgency")], "Y": [M("Labelled Reviews")]},
          title="Urgency")
    p.add("matrix", "pivotTable", 848, 196, 408, 260,
          query={"Rows": [C("dim_product.category")], "Columns": [topic],
                 "Values": [M("Negative Reviews (AI)")]},
          sort=[(M("Negative Reviews (AI)"), "Descending")],
          title="Complaints by product category and topic")
    p.add("reviews", "tableEx", 24, 468, 1232, 236,
          query={"Values": [C("review_ai_labels.Stars"), topic, C("review_ai_labels.urgency"),
                            C("review_ai_labels.summary_en"), C("review_ai_labels.Review text")]},
          sort=[(C("review_ai_labels.urgency"), "Ascending")],
          filters=[in_filter("negativeOnly", C("review_ai_labels.sentiment"), ["negative"])],
          title="Negative reviews: AI summary next to the original text")
    pages.append(p)

    # ---- Page 4: Seller watch-list -------------------------------------------
    p = Page("sellers", "Seller watch-list")
    p.header("Seller watch-list",
             "Sellers with 100+ delivered orders, lowest average review score first")
    p.add("sellers", "tableEx", 24, 84, 760, 620,
          query={"Values": [C("dim_seller.seller_id"), C("dim_seller.state"), M("Delivered Orders"),
                            M("Revenue"), M("Late Delivery %"), M("Avg Review Score")]},
          sort=[(M("Avg Review Score"), "Ascending")],
          filters=[at_least_filter("min100Orders", "Delivered Orders", 100)],
          title="Sellers to talk to first")
    p.add("seller_state", "clusteredBarChart", 796, 84, 460, 620,
          query={"Category": [C("dim_seller.state")], "Y": [M("Avg Review Score")]},
          sort=[(M("Avg Review Score"), "Ascending")], objects=data_labels(),
          title="Average review score by seller state")
    pages.append(p)
    return pages


def build_report() -> None:
    write_json(REPORT_DIR / ".platform", {
        "$schema": f"{SCHEMA}/gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {"type": "Report", "displayName": NAME},
        "config": {"version": "2.0", "logicalId": stable_id("report")},
    })
    write_json(REPORT_DIR / "definition.pbir", {
        "$schema": f"{SCHEMA}/item/report/definitionProperties/2.0.0/schema.json",
        "version": "4.0",
        "datasetReference": {"byPath": {"path": f"../{NAME}.SemanticModel"}},
    })
    d = REPORT_DIR / "definition"
    write_json(d / "version.json", {
        "$schema": f"{SCHEMA}/item/report/definition/versionMetadata/1.0.0/schema.json",
        "version": "2.0.0",
    })
    theme_file = "AICustomerInsights.json"
    write_json(REPORT_DIR / "StaticResources" / "RegisteredResources" / theme_file, {
        "name": "AI Customer Insights",
        "dataColors": ["#1F4E79", "#E07A1F", "#2E8B57", "#C0392B", "#7A869A",
                       "#8E6CBF", "#17A2B8", "#C9A227"],
        "foreground": "#1F2937",
        "background": "#FFFFFF",
        "tableAccent": "#1F4E79",
        "good": "#2E8B57",
        "neutral": "#C9A227",
        "bad": "#C0392B",
    })
    write_json(d / "report.json", {
        "$schema": f"{SCHEMA}/item/report/definition/report/1.3.0/schema.json",
        "themeCollection": {
            "baseTheme": {"name": "CY24SU10", "reportVersionAtImport": "5.61",
                          "type": "SharedResources"},
            "customTheme": {"name": theme_file, "reportVersionAtImport": "5.61",
                            "type": "RegisteredResources"},
        },
        "layoutOptimization": "None",
        "resourcePackages": [
            {"name": "SharedResources", "type": "SharedResources",
             "items": [{"name": "CY24SU10", "path": "BaseThemes/CY24SU10.json",
                        "type": "BaseTheme"}]},
            {"name": "RegisteredResources", "type": "RegisteredResources",
             "items": [{"name": theme_file, "path": theme_file, "type": "CustomTheme"}]},
        ],
        "settings": {
            "useStylableVisualContainerHeader": True,
            "exportDataMode": "AllowSummarizedAndUnderlying",
            "defaultDrillFilterOtherVisuals": True,
            "allowChangeFilterTypes": True,
            "useEnhancedTooltips": True,
        },
    })
    pages = build_pages()
    write_json(d / "pages" / "pages.json", {
        "$schema": f"{SCHEMA}/item/report/definition/pagesMetadata/1.0.0/schema.json",
        "pageOrder": [p.name for p in pages],
        "activePageName": pages[0].name,
    })
    for p in pages:
        write_json(d / "pages" / p.name / "page.json", p.json())
        for v in p.visuals:
            write_json(d / "pages" / p.name / "visuals" / v["name"] / "visual.json", v)


def main() -> None:
    # Start clean, but keep the base theme that ships with Power BI
    shutil.rmtree(MODEL_DIR, ignore_errors=True)
    shutil.rmtree(REPORT_DIR / "definition", ignore_errors=True)
    shutil.rmtree(REPORT_DIR / "StaticResources" / "RegisteredResources", ignore_errors=True)
    build_model()
    build_report()
    write_json(OUT / f"{NAME}.pbip", {
        "$schema": f"{SCHEMA}/pbip/pbipProperties/1.0.0/schema.json",
        "version": "1.0",
        "artifacts": [{"report": {"path": f"{NAME}.Report"}}],
        "settings": {"enableAutoRecovery": True},
    })
    write(OUT / ".gitignore", "**/.pbi/localSettings.json\n**/.pbi/cache.abf\n")
    print(f"Power BI project ready: {OUT / (NAME + '.pbip')}")


if __name__ == "__main__":
    main()
