# Interview guide for this project

## 30-second pitch
"I built an analytics project on 100,000 real e-commerce orders. SQL and Power BI showed that late
deliveries are the main driver of bad reviews: late orders average 2.6 stars versus 4.3. But managers
couldn't see *why* customers were unhappy, because the reasons were buried in 40,000 written reviews in
Portuguese. So I used a free open-source LLM to classify every review by sentiment, topic and urgency, and
I measured its accuracy against reviews I labelled by hand instead of just trusting it. I also built a
Streamlit app where anyone can ask questions in plain English. The AI writes SQL, but guardrails make
sure it can only run safe, read-only queries."

## CV bullets (update the numbers after your LLM run)
- Built an end-to-end analytics pipeline (Python, SQL, Power BI, Excel) on 99k e-commerce orders; identified late delivery as the main driver of 1–2★ reviews (54% of late orders vs 9% on time).
- Used an open-source LLM (Ollama) to classify 40k Portuguese customer reviews into sentiment, complaint topic and urgency; validated against 150 hand-labelled reviews (**XX%** topic accuracy vs 55% keyword baseline).
- Developed a natural-language "ask your data" app (Streamlit, text-to-SQL) with guardrails: SELECT-only, table allow-list, read-only connection, query timeout.
- Designed a Power BI star-schema model with DAX time-intelligence measures and an Excel KPI pack with an AI-drafted, analyst-reviewed executive summary.

## Questions you will be asked (practise answering)
1. **Why didn't you just trust the AI?** LLMs make confident mistakes. I compared it with star ratings and with my own labels, looked at the confusion matrix, and checked where it disagrees.
2. **Why does sentiment vs stars score lower than vs your labels?** Stars and text disagree: 5★ with "arrived late but OK", or 1★ with "haven't received it yet".
3. **What happens if the AI writes `DROP TABLE`?** Two layers: the validator only accepts a single SELECT on allowed tables, and the database is opened read-only, so even a missed case can't change data (there's a test for this).
4. **Why a star schema?** Fast, simple filtering in Power BI; facts (orders, items, reviews) join to dimensions (customer, product, seller, date).
5. **Explain this DAX:** `Revenue MoM %`, `DATEADD`, and why `dim_date` must be marked as a date table.
6. **Explain this SQL:** Q7 uses `ROW_NUMBER() OVER (PARTITION BY customer ORDER BY purchase)` to find each customer's first order.
7. **Why Ollama instead of ChatGPT?** It's free, private (data never leaves the laptop) and reproducible (temperature 0, fixed model).
8. **What would you improve?** More hand labels, try a larger model, predict late deliveries before they happen.

## Before an interview, make sure you can
- Run `python run_all.py` and `streamlit run app/streamlit_app.py` from scratch
- Open `results/evaluation.md` and explain one mistake the AI made
- Rebuild one DAX measure live
