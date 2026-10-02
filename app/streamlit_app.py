"""AI Customer Insights - Streamlit app.

    streamlit run app/streamlit_app.py

Tabs: Overview | Ask your data (AI text-to-SQL) | Review insights (AI labels) | AI quality
"""
import sqlite3
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import requests
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src import config  # noqa: E402
from src.bootstrap import ensure_database  # noqa: E402
from src.llm import LLMError  # noqa: E402
from src.sql_guard import UnsafeSQLError, run_readonly, validate_sql  # noqa: E402
from src.text_to_sql import ask_data  # noqa: E402

st.set_page_config(page_title="AI Customer Insights", page_icon="📦", layout="wide")

with st.spinner("First run: downloading data and building the database (~1 minute)..."):
    ensure_database()


@st.cache_data(show_spinner=False)
def q(sql: str) -> pd.DataFrame:
    con = sqlite3.connect(f"file:{config.DB_PATH}?mode=ro", uri=True)
    try:
        return pd.read_sql_query(sql, con)
    finally:
        con.close()


# Questions that work without any AI (demo mode / Streamlit Cloud without a key)
DEMO_QUESTIONS = {
    "Which 5 states have the highest late-delivery rate?":
        """SELECT c.state, COUNT(*) AS orders, ROUND(100.0*AVG(o.is_late),1) AS late_pct
FROM fact_orders o JOIN dim_customer c ON c.customer_id = o.customer_id
WHERE o.order_status = 'delivered' GROUP BY c.state HAVING COUNT(*) >= 300
ORDER BY late_pct DESC LIMIT 5""",
    "What is the average review score for late vs on-time deliveries?":
        """SELECT CASE WHEN o.is_late = 1 THEN 'Late' ELSE 'On time' END AS delivery,
ROUND(AVG(r.review_score), 2) AS avg_score, COUNT(*) AS reviews
FROM fact_reviews r JOIN fact_orders o ON o.order_id = r.order_id
WHERE o.order_status = 'delivered' AND o.is_late IS NOT NULL GROUP BY delivery""",
    "What are the most common complaint topics?":
        """SELECT topic, COUNT(*) AS negative_reviews FROM review_ai_labels
WHERE sentiment = 'negative' GROUP BY topic ORDER BY negative_reviews DESC""",
    "Top 10 categories by revenue":
        """SELECT p.category, ROUND(SUM(i.price), 0) AS revenue
FROM fact_order_items i JOIN dim_product p ON p.product_id = i.product_id
JOIN fact_orders o ON o.order_id = i.order_id WHERE o.order_status = 'delivered'
GROUP BY p.category ORDER BY revenue DESC LIMIT 10""",
    "Monthly orders in 2018":
        """SELECT d.year_month, COUNT(*) AS orders FROM fact_orders o
JOIN dim_date d ON d.date_key = o.purchase_date
WHERE d.year = 2018 AND o.order_status = 'delivered' GROUP BY d.year_month ORDER BY d.year_month""",
}


def provider_status(provider: str) -> tuple[bool, str]:
    if provider == "ollama":
        try:
            tags = requests.get(f"{config.OLLAMA_URL}/api/tags", timeout=2).json()
            models = [m["name"] for m in tags.get("models", [])]
            if not any(m.startswith(config.OLLAMA_MODEL.split(":")[0]) for m in models):
                return False, f"Ollama is running but `{config.OLLAMA_MODEL}` isn't pulled."
            return True, f"Ollama · {config.OLLAMA_MODEL}"
        except requests.RequestException:
            return False, "Ollama is not running on this machine."
    key = {"groq": config.GROQ_API_KEY, "gemini": config.GEMINI_API_KEY}.get(provider)
    model = {"groq": config.GROQ_MODEL, "gemini": config.GEMINI_MODEL}.get(provider)
    return (bool(key), f"{provider} · {model}" if key else f"No {provider.upper()}_API_KEY set.")


def auto_chart(df: pd.DataFrame):
    if len(df) < 2 or df.shape[1] < 2:
        return None
    num = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    cat = [c for c in df.columns if c not in num]
    if not num or not cat:
        return None
    x, y = cat[0], num[-1]
    if "month" in x or "date" in x:
        return px.line(df, x=x, y=y, markers=True)
    return px.bar(df, x=x, y=y)


# ------------------------------------------------------------------ sidebar
with st.sidebar:
    st.title("📦 AI Customer Insights")
    st.caption("Olist e-commerce · 99k orders · 2016-2018")
    provider = st.selectbox("AI provider (all free)", ["ollama", "groq", "gemini"],
                            index=["ollama", "groq", "gemini"].index(config.LLM_PROVIDER)
                            if config.LLM_PROVIDER in ("ollama", "groq", "gemini") else 0)
    ai_ok, ai_msg = provider_status(provider)
    (st.success if ai_ok else st.warning)(ai_msg)
    if not ai_ok:
        st.caption("Demo mode: 'Ask your data' uses saved example questions. "
                   "See the README to switch on free AI.")
    labels_by = q("SELECT provider, COUNT(*) n FROM review_ai_labels GROUP BY provider")
    if len(labels_by):
        st.caption(f"Review labels from: **{labels_by.provider[0]}** ({labels_by.n[0]:,} reviews)")

tab_overview, tab_ask, tab_reviews, tab_quality = st.tabs(
    ["📊 Overview", "💬 Ask your data", "📝 Review insights", "✅ AI quality"])

# ------------------------------------------------------------------ overview
with tab_overview:
    k = q("""SELECT COUNT(*) orders, SUM(order_value) revenue, AVG(order_value) aov,
             AVG(delivery_days) days, AVG(is_late) late FROM fact_orders
             WHERE order_status='delivered'""").iloc[0]
    score = q("SELECT AVG(review_score) s FROM fact_reviews").s[0]
    c = st.columns(5)
    c[0].metric("Delivered orders", f"{k.orders:,.0f}")
    c[1].metric("Revenue (BRL)", f"{k.revenue / 1e6:,.2f}M")
    c[2].metric("Avg order value", f"R$ {k.aov:,.0f}")
    c[3].metric("Late deliveries", f"{k.late:.1%}")
    c[4].metric("Avg review score", f"{score:.2f} ★")

    left, right = st.columns(2)
    monthly = q("""SELECT d.year_month, SUM(o.order_value) revenue FROM fact_orders o
                   JOIN dim_date d ON d.date_key=o.purchase_date
                   WHERE o.order_status='delivered' AND d.year_month BETWEEN '2017-01' AND '2018-08'
                   GROUP BY d.year_month""")
    left.plotly_chart(px.line(monthly, x="year_month", y="revenue", markers=True,
                              title="Monthly revenue (BRL)"), width="stretch")
    late = q("""SELECT CASE WHEN days_late<=-7 THEN '7+ days early' WHEN days_late<=0 THEN '0-7 days early'
                WHEN days_late<=3 THEN '1-3 days late' WHEN days_late<=7 THEN '4-7 days late'
                ELSE '8+ days late' END bucket, AVG(r.review_score) avg_score, MIN(days_late) o
                FROM fact_reviews r JOIN fact_orders o ON o.order_id=r.order_id
                WHERE o.order_status='delivered' AND days_late IS NOT NULL GROUP BY bucket ORDER BY o""")
    right.plotly_chart(px.bar(late, x="bucket", y="avg_score", range_y=[1, 5],
                              title="Review score falls sharply once an order is late"),
                       width="stretch")
    state = q("""SELECT c.state, AVG(o.is_late)*100 late_pct, COUNT(*) n FROM fact_orders o
                 JOIN dim_customer c ON c.customer_id=o.customer_id WHERE o.order_status='delivered'
                 GROUP BY c.state HAVING n>=300 ORDER BY late_pct DESC""")
    st.plotly_chart(px.bar(state, x="state", y="late_pct", title="Late-delivery rate by customer state (%)"),
                    width="stretch")

# ------------------------------------------------------------------ ask your data
with tab_ask:
    st.subheader("Ask a business question in plain English")
    st.caption("The AI writes SQL → guardrails check it (SELECT-only, allowed tables, row limit) → "
               "it runs on a read-only connection → the AI explains the result. "
               "Always check the SQL before trusting the answer.")
    example = st.selectbox("Try an example", ["(type your own)"] + list(DEMO_QUESTIONS))
    question = st.text_input("Your question",
                             value="" if example == "(type your own)" else example,
                             placeholder="e.g. Which sellers in SP have the worst average rating?")
    if st.button("Ask", type="primary") and question.strip():
        if ai_ok:
            with st.spinner("Thinking..."):
                try:
                    ans = ask_data(question, provider=provider)
                except LLMError as exc:
                    st.error(str(exc))
                    st.stop()
            st.code(ans.sql, language="sql")
            if ans.error:
                st.error(f"Could not answer safely: {ans.error}")
            else:
                df = pd.DataFrame(ans.rows, columns=ans.columns)
                if ans.explanation:
                    st.info(ans.explanation)
                fig = auto_chart(df)
                if fig is not None:
                    st.plotly_chart(fig, width="stretch")
                st.dataframe(df, width="stretch")
                st.caption(f"Answered in {ans.attempts} attempt(s).")
        elif question in DEMO_QUESTIONS:
            sql = validate_sql(DEMO_QUESTIONS[question])
            st.code(sql, language="sql")
            cols, rows = run_readonly(config.DB_PATH, sql)
            df = pd.DataFrame(rows, columns=cols)
            fig = auto_chart(df)
            if fig is not None:
                st.plotly_chart(fig, width="stretch")
            st.dataframe(df, width="stretch")
            st.caption("Demo mode: pre-written SQL. Switch on a free AI provider to ask anything.")
        else:
            st.warning("No AI provider is available, so only the example questions work. "
                       "Start Ollama or add a free Groq/Gemini key (see README).")

    with st.expander("Try to break it: paste any SQL and see the guardrails"):
        test_sql = st.text_area("SQL", "DELETE FROM fact_orders")
        if st.button("Check"):
            try:
                st.success("Allowed. This is what would run:")
                st.code(validate_sql(test_sql), language="sql")
            except UnsafeSQLError as exc:
                st.error(f"Blocked: {exc}")

# ------------------------------------------------------------------ review insights
with tab_reviews:
    st.subheader("What are customers actually complaining about?")
    st.caption("Each written review (Portuguese) was classified by AI into sentiment, topic and urgency.")
    topics = q("""SELECT topic, COUNT(*) reviews, AVG(r.review_score) avg_score
                  FROM review_ai_labels l JOIN fact_reviews r USING (review_id, order_id)
                  WHERE l.sentiment='negative' GROUP BY topic ORDER BY reviews DESC""")
    if topics.empty:
        st.info("No labels yet. Run `python scripts/03_label_reviews.py`.")
    else:
        a, b = st.columns(2)
        a.plotly_chart(px.bar(topics, x="reviews", y="topic", orientation="h",
                              title="Complaint topics (negative reviews)").update_yaxes(
            categoryorder="total ascending"), width="stretch")
        urg = q("""SELECT urgency, COUNT(*) reviews FROM review_ai_labels GROUP BY urgency""")
        b.plotly_chart(px.pie(urg, names="urgency", values="reviews", hole=0.5,
                              title="Urgency of all labelled reviews"), width="stretch")
        cat = q("""SELECT p.category, l.topic, COUNT(*) n FROM review_ai_labels l
                   JOIN fact_order_items i ON i.order_id=l.order_id AND i.order_item_id=1
                   JOIN dim_product p ON p.product_id=i.product_id
                   WHERE l.sentiment='negative' GROUP BY p.category, l.topic""")
        top_cats = cat.groupby("category").n.sum().nlargest(10).index
        st.plotly_chart(px.density_heatmap(cat[cat.category.isin(top_cats)], x="topic", y="category",
                                           z="n", title="Complaint topics × top 10 categories",
                                           color_continuous_scale="Reds"), width="stretch")

        st.markdown("#### Browse labelled reviews")
        f1, f2 = st.columns(2)
        pick_topic = f1.multiselect("Topic", sorted(topics.topic))
        pick_urg = f2.multiselect("Urgency", ["high", "medium", "low"], default=["high"])
        browse = q("""SELECT r.review_score stars, l.sentiment, l.topic, l.urgency,
                      l.summary_en, r.comment_message FROM review_ai_labels l
                      JOIN fact_reviews r USING (review_id, order_id)""")
        if pick_topic:
            browse = browse[browse.topic.isin(pick_topic)]
        if pick_urg:
            browse = browse[browse.urgency.isin(pick_urg)]
        st.dataframe(browse.head(300), width="stretch", hide_index=True)

# ------------------------------------------------------------------ AI quality
with tab_quality:
    st.subheader("How accurate is the AI? (measured, not assumed)")
    summary_file = config.RESULTS_DIR / "evaluation_summary.csv"
    if summary_file.exists():
        ev = pd.read_csv(summary_file)
        show = ev.copy()
        for col in show.columns:
            if col.endswith(("acc", "f1")):
                show[col] = (show[col] * 100).round(1).astype(str) + "%"
        st.dataframe(show, width="stretch", hide_index=True)
        st.markdown(
            "- **sentiment_vs_stars**: AI sentiment vs the customer's own star rating.\n"
            "- **gold_***: vs 150 reviews labelled by hand.\n"
            "- **complaint_topic_acc**: topic accuracy on negative reviews — the ones the business acts on.\n"
            "- `rules` is a keyword baseline with no AI: the LLM has to beat it to be worth using.")
        report = config.RESULTS_DIR / "evaluation.md"
        if report.exists():
            with st.expander("Full evaluation report (confusion matrices, disagreements)"):
                st.markdown(report.read_text(encoding="utf-8"))
    else:
        st.info("Run `python scripts/04_evaluate.py` to measure accuracy.")
