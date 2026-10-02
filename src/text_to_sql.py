"""Natural-language question -> SQL -> answer, using a free LLM.

Flow:  question -> LLM writes SQL (given the schema + examples)
       -> guardrails (src/sql_guard.py) -> read-only execution
       -> if SQL errors, send the error back to the LLM once to fix it
       -> LLM writes a 1-2 sentence plain-English answer from the result rows
The SQL is always shown to the user so a human can check it.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from src.config import DB_PATH
from src.labels import TOPICS
from src.llm import ask_llm
from src.sql_guard import extract_sql, run_readonly, validate_sql

SCHEMA = f"""SQLite database of a Brazilian e-commerce marketplace (2016-2018). Money is in BRL.

fact_orders(order_id, customer_id, order_status, purchase_ts, purchase_date 'YYYY-MM-DD',
            delivered_ts, estimated_delivery_ts, delivery_days, days_late, is_late 0/1,
            order_value, freight_value, payment_type, installments)
fact_order_items(order_id, order_item_id, product_id, seller_id, price, freight_value)
fact_reviews(review_id, order_id, review_score 1-5, comment_title, comment_message, review_date)
review_ai_labels(review_id, order_id, sentiment, topic, urgency, summary_en)   -- AI labels of review text
dim_customer(customer_id, customer_unique_id, city, state)   -- state = 2-letter code e.g. 'SP'
dim_product(product_id, category, weight_g, photos_qty)      -- category in English snake_case
dim_seller(seller_id, city, state)
dim_date(date_key, year, quarter, month, month_name, year_month 'YYYY-MM', weekday)

Rules:
- Use order_status = 'delivered' for sales/delivery questions unless asked otherwise.
- Join reviews to orders on order_id; labels to reviews on (review_id, order_id).
- sentiment is one of positive/neutral/negative; topic is one of {list(TOPICS)}.
- Round decimals with ROUND(x, 2). Always add LIMIT for lists.
"""

EXAMPLES = """Q: What is the average review score by payment type?
SQL: SELECT o.payment_type, ROUND(AVG(r.review_score), 2) AS avg_score, COUNT(*) AS reviews
FROM fact_reviews r JOIN fact_orders o ON o.order_id = r.order_id
GROUP BY o.payment_type ORDER BY avg_score DESC

Q: Top 5 categories by revenue in 2018
SQL: SELECT p.category, ROUND(SUM(i.price), 0) AS revenue
FROM fact_order_items i JOIN dim_product p ON p.product_id = i.product_id
JOIN fact_orders o ON o.order_id = i.order_id
WHERE o.order_status = 'delivered' AND o.purchase_date LIKE '2018%'
GROUP BY p.category ORDER BY revenue DESC LIMIT 5"""

SQL_SYSTEM = ("You are an expert SQLite analyst. Write ONE SQLite SELECT query that answers the "
              "question. Return only the SQL inside a ```sql block.\n\n" + SCHEMA +
              "\nExamples:\n" + EXAMPLES)

ANSWER_SYSTEM = ("You are a business analyst. Using ONLY the query result given, answer the "
                 "question in 1-2 plain-English sentences with the key numbers. "
                 "Do not invent numbers that are not in the result.")


@dataclass
class Answer:
    question: str
    sql: str = ""
    columns: list = field(default_factory=list)
    rows: list = field(default_factory=list)
    explanation: str = ""
    error: str = ""
    attempts: int = 0


def ask_data(question: str, provider: str | None = None, explain: bool = True) -> Answer:
    ans = Answer(question)
    prompt = f"Q: {question}\nSQL:"
    for attempt in range(2):  # one automatic self-correction
        ans.attempts = attempt + 1
        raw = ask_llm(SQL_SYSTEM, prompt, provider=provider, json_mode=False)
        ans.sql = extract_sql(raw)
        try:
            safe = validate_sql(ans.sql)
            ans.columns, ans.rows = run_readonly(DB_PATH, safe)
            ans.sql, ans.error = safe, ""
            break
        except Exception as exc:  # noqa: BLE001 - show any DB/guard error to the model once
            ans.error = str(exc)
            prompt = (f"Q: {question}\nYour previous SQL:\n{ans.sql}\n"
                      f"failed with: {exc}\nWrite a corrected query.\nSQL:")
    if ans.error or not explain:
        return ans

    preview = "\n".join([", ".join(ans.columns)] + [", ".join(map(str, r)) for r in ans.rows[:20]])
    ans.explanation = ask_llm(ANSWER_SYSTEM, f"Question: {question}\nResult:\n{preview}",
                              provider=provider, json_mode=False).strip()
    return ans
