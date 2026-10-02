-- =============================================================
-- Business analysis queries (SQLite; PostgreSQL notes inline)
-- Run all of them with: python scripts/run_sql_analysis.py
-- Each query answers one business question a manager would ask.
-- =============================================================

-- name: q01_kpi_overview
-- Q1. Headline KPIs for delivered orders.
SELECT
    COUNT(*)                                        AS delivered_orders,
    COUNT(DISTINCT c.customer_unique_id)            AS customers,
    ROUND(SUM(o.order_value), 0)                    AS revenue_brl,
    ROUND(AVG(o.order_value), 2)                    AS avg_order_value,
    ROUND(AVG(o.delivery_days), 1)                  AS avg_delivery_days,
    ROUND(100.0 * AVG(o.is_late), 1)                AS late_delivery_pct
FROM fact_orders o
JOIN dim_customer c ON c.customer_id = o.customer_id
WHERE o.order_status = 'delivered';

-- name: q02_monthly_revenue_growth
-- Q2. Monthly revenue with month-over-month growth (window function LAG).
WITH monthly AS (
    SELECT d.year_month,
           SUM(o.order_value) AS revenue,
           COUNT(*)           AS orders
    FROM fact_orders o
    JOIN dim_date d ON d.date_key = o.purchase_date
    WHERE o.order_status = 'delivered'
    GROUP BY d.year_month
)
SELECT year_month,
       orders,
       ROUND(revenue, 0) AS revenue,
       ROUND(100.0 * (revenue - LAG(revenue) OVER (ORDER BY year_month))
             / LAG(revenue) OVER (ORDER BY year_month), 1) AS mom_growth_pct
FROM monthly
WHERE year_month BETWEEN '2017-01' AND '2018-08'   -- full months only
ORDER BY year_month;

-- name: q03_late_delivery_vs_rating
-- Q3. THE key question: does a late delivery hurt the review score?
SELECT
    CASE WHEN o.is_late = 1 THEN 'Late' ELSE 'On time' END AS delivery,
    COUNT(*)                                   AS reviews,
    ROUND(AVG(r.review_score), 2)              AS avg_score,
    ROUND(100.0 * AVG(r.review_score <= 2), 1) AS pct_1_2_stars
FROM fact_reviews r
JOIN fact_orders o ON o.order_id = r.order_id
WHERE o.order_status = 'delivered' AND o.is_late IS NOT NULL
GROUP BY delivery;

-- name: q04_rating_by_days_late
-- Q4. How the rating falls as lateness grows (bucketing with CASE).
SELECT
    CASE
        WHEN o.days_late <= -7 THEN '1. 7+ days early'
        WHEN o.days_late <= 0  THEN '2. 0-7 days early'
        WHEN o.days_late <= 3  THEN '3. 1-3 days late'
        WHEN o.days_late <= 7  THEN '4. 4-7 days late'
        ELSE                        '5. 8+ days late'
    END AS lateness_bucket,
    COUNT(*)                      AS reviews,
    ROUND(AVG(r.review_score), 2) AS avg_score
FROM fact_reviews r
JOIN fact_orders o ON o.order_id = r.order_id
WHERE o.order_status = 'delivered' AND o.days_late IS NOT NULL
GROUP BY lateness_bucket
ORDER BY lateness_bucket;

-- name: q05_category_scorecard
-- Q5. Category scorecard: revenue, rating and late rate, ranked (RANK window).
WITH cat AS (
    SELECT p.category,
           SUM(i.price)                     AS revenue,
           COUNT(DISTINCT i.order_id)       AS orders,
           AVG(r.review_score)              AS avg_score,
           AVG(o.is_late)                   AS late_rate
    FROM fact_order_items i
    JOIN dim_product p ON p.product_id = i.product_id
    JOIN fact_orders o ON o.order_id = i.order_id
    LEFT JOIN fact_reviews r ON r.order_id = i.order_id
    WHERE o.order_status = 'delivered'
    GROUP BY p.category
    HAVING COUNT(DISTINCT i.order_id) >= 500
)
SELECT RANK() OVER (ORDER BY revenue DESC) AS revenue_rank,
       category,
       orders,
       ROUND(revenue, 0)          AS revenue,
       ROUND(avg_score, 2)        AS avg_score,
       ROUND(100.0 * late_rate,1) AS late_pct
FROM cat
ORDER BY revenue_rank
LIMIT 15;

-- name: q06_state_delivery_performance
-- Q6. Which customer states wait longest and are most often late?
SELECT c.state,
       COUNT(*)                         AS orders,
       ROUND(AVG(o.delivery_days), 1)   AS avg_delivery_days,
       ROUND(100.0 * AVG(o.is_late), 1) AS late_pct,
       ROUND(AVG(r.review_score), 2)    AS avg_score
FROM fact_orders o
JOIN dim_customer c ON c.customer_id = o.customer_id
LEFT JOIN fact_reviews r ON r.order_id = o.order_id
WHERE o.order_status = 'delivered'
GROUP BY c.state
HAVING COUNT(*) >= 300
ORDER BY late_pct DESC;

-- name: q07_repeat_purchase_after_bad_review
-- Q7. Do unhappy customers come back? First-order rating vs repeat purchase.
WITH ranked AS (
    SELECT c.customer_unique_id,
           o.order_id,
           o.purchase_ts,
           ROW_NUMBER() OVER (PARTITION BY c.customer_unique_id ORDER BY o.purchase_ts) AS order_no,
           COUNT(*)     OVER (PARTITION BY c.customer_unique_id)                         AS total_orders
    FROM fact_orders o
    JOIN dim_customer c ON c.customer_id = o.customer_id
    WHERE o.order_status = 'delivered'
),
first_orders AS (
    SELECT f.customer_unique_id, f.total_orders, r.review_score
    FROM ranked f
    JOIN fact_reviews r ON r.order_id = f.order_id
    WHERE f.order_no = 1
)
SELECT CASE WHEN review_score <= 2 THEN '1-2 stars'
            WHEN review_score = 3  THEN '3 stars'
            ELSE '4-5 stars' END            AS first_order_rating,
       COUNT(*)                             AS customers,
       ROUND(100.0 * AVG(total_orders > 1), 2) AS repeat_rate_pct
FROM first_orders
GROUP BY first_order_rating
ORDER BY first_order_rating;

-- name: q08_top_sellers_with_problems
-- Q8. High-volume sellers with poor ratings (who should account managers call?).
SELECT i.seller_id,
       s.state                          AS seller_state,
       COUNT(DISTINCT i.order_id)       AS orders,
       ROUND(AVG(r.review_score), 2)    AS avg_score,
       ROUND(100.0 * AVG(o.is_late), 1) AS late_pct
FROM fact_order_items i
JOIN dim_seller s  ON s.seller_id = i.seller_id
JOIN fact_orders o ON o.order_id = i.order_id
JOIN fact_reviews r ON r.order_id = i.order_id
WHERE o.order_status = 'delivered'
GROUP BY i.seller_id, s.state
HAVING COUNT(DISTINCT i.order_id) >= 100
ORDER BY avg_score ASC
LIMIT 10;

-- name: q09_ai_topic_breakdown
-- Q9. (Needs AI labels) What are customers complaining about?
SELECT l.topic,
       COUNT(*)                                    AS reviews,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS share_pct,
       ROUND(AVG(r.review_score), 2)               AS avg_score
FROM review_ai_labels l
JOIN fact_reviews r ON r.review_id = l.review_id AND r.order_id = l.order_id
WHERE l.sentiment = 'negative'
GROUP BY l.topic
ORDER BY reviews DESC;

-- name: q10_ai_topic_by_category
-- Q10. (Needs AI labels) Complaint topics per product category (top categories).
SELECT p.category,
       l.topic,
       COUNT(DISTINCT l.review_id) AS negative_reviews
FROM review_ai_labels l
JOIN fact_order_items i ON i.order_id = l.order_id AND i.order_item_id = 1
JOIN dim_product p      ON p.product_id = i.product_id
WHERE l.sentiment = 'negative'
GROUP BY p.category, l.topic
HAVING COUNT(DISTINCT l.review_id) >= 5
ORDER BY negative_reviews DESC
LIMIT 20;
