-- =============================================================
-- Star schema for the AI Customer Insights project (SQLite)
-- Facts: fact_order_items, fact_orders, fact_reviews
-- Dimensions: dim_customer, dim_product, dim_seller, dim_date
-- AI output: review_ai_labels (filled by scripts/03_label_reviews.py)
-- =============================================================

DROP TABLE IF EXISTS dim_customer;
CREATE TABLE dim_customer (
    customer_id         TEXT PRIMARY KEY,   -- one per order in Olist
    customer_unique_id  TEXT NOT NULL,      -- the real person (use for repeat-purchase analysis)
    city                TEXT,
    state               TEXT
);

DROP TABLE IF EXISTS dim_product;
CREATE TABLE dim_product (
    product_id      TEXT PRIMARY KEY,
    category        TEXT,                   -- English category name
    weight_g        REAL,
    photos_qty      INTEGER
);

DROP TABLE IF EXISTS dim_seller;
CREATE TABLE dim_seller (
    seller_id   TEXT PRIMARY KEY,
    city        TEXT,
    state       TEXT
);

DROP TABLE IF EXISTS dim_date;
CREATE TABLE dim_date (
    date_key    TEXT PRIMARY KEY,           -- 'YYYY-MM-DD'
    year        INTEGER,
    quarter     INTEGER,
    month       INTEGER,
    month_name  TEXT,
    year_month  TEXT,
    weekday     TEXT
);

DROP TABLE IF EXISTS fact_orders;
CREATE TABLE fact_orders (
    order_id                TEXT PRIMARY KEY,
    customer_id             TEXT REFERENCES dim_customer(customer_id),
    order_status            TEXT,
    purchase_ts             TEXT,
    purchase_date           TEXT REFERENCES dim_date(date_key),
    delivered_ts            TEXT,
    estimated_delivery_ts   TEXT,
    delivery_days           REAL,           -- purchase -> delivered
    days_late               REAL,           -- delivered - estimated (positive = late)
    is_late                 INTEGER,        -- 1 if delivered after the estimate
    order_value             REAL,           -- sum of item price
    freight_value           REAL,
    payment_type            TEXT,
    installments            INTEGER
);

DROP TABLE IF EXISTS fact_order_items;
CREATE TABLE fact_order_items (
    order_id        TEXT REFERENCES fact_orders(order_id),
    order_item_id   INTEGER,
    product_id      TEXT REFERENCES dim_product(product_id),
    seller_id       TEXT REFERENCES dim_seller(seller_id),
    price           REAL,
    freight_value   REAL,
    PRIMARY KEY (order_id, order_item_id)
);

DROP TABLE IF EXISTS fact_reviews;
CREATE TABLE fact_reviews (
    review_id       TEXT,
    order_id        TEXT REFERENCES fact_orders(order_id),
    review_score    INTEGER,                -- 1-5 stars
    comment_title   TEXT,
    comment_message TEXT,                   -- Portuguese free text
    review_date     TEXT,
    PRIMARY KEY (review_id, order_id)
);

-- Filled by the AI labelling step
CREATE TABLE IF NOT EXISTS review_ai_labels (
    review_id       TEXT,
    order_id        TEXT,
    sentiment       TEXT,                   -- positive / neutral / negative
    topic           TEXT,                   -- see src/labels.py
    urgency         TEXT,                   -- low / medium / high
    summary_en      TEXT,                   -- one-line English summary
    provider        TEXT,                   -- which AI produced the label
    PRIMARY KEY (review_id, order_id)
);

CREATE INDEX IF NOT EXISTS ix_orders_customer ON fact_orders(customer_id);
CREATE INDEX IF NOT EXISTS ix_orders_date ON fact_orders(purchase_date);
CREATE INDEX IF NOT EXISTS ix_items_product ON fact_order_items(product_id);
CREATE INDEX IF NOT EXISTS ix_reviews_order ON fact_reviews(order_id);
