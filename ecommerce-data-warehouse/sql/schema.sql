-- =====================================================
-- STAR SCHEMA FOR BRAZILIAN E-COMMERCE (OLIST)
-- Fact and dimension tables optimized for analytics
-- =====================================================

-- Drop existing tables
DROP TABLE IF EXISTS fact_orders CASCADE;
DROP TABLE IF EXISTS dim_customer CASCADE;
DROP TABLE IF EXISTS dim_product CASCADE;
DROP TABLE IF EXISTS dim_seller CASCADE;
DROP TABLE IF EXISTS dim_date CASCADE;
DROP TABLE IF EXISTS dim_geolocation CASCADE;

-- =====================================================
-- DIMENSION TABLES
-- =====================================================

-- 1. Dim Customer (SCD Type 2)
CREATE TABLE dim_customer (
    customer_key SERIAL PRIMARY KEY,
    customer_id VARCHAR(50) NOT NULL,
    customer_unique_id VARCHAR(50),
    customer_zip_code_prefix VARCHAR(10),
    customer_city VARCHAR(100),
    customer_state CHAR(2),
    -- SCD2 columns
    valid_from DATE NOT NULL DEFAULT CURRENT_DATE,
    valid_to DATE,
    is_current BOOLEAN DEFAULT TRUE,
    version INTEGER DEFAULT 1,
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uk_customer_scd2 UNIQUE (customer_id, version)
);

CREATE INDEX idx_customer_current ON dim_customer(is_current) WHERE is_current = TRUE;
CREATE INDEX idx_customer_city ON dim_customer(customer_city);
CREATE INDEX idx_customer_state ON dim_customer(customer_state);

-- 2. Dim Product
CREATE TABLE dim_product (
    product_key SERIAL PRIMARY KEY,
    product_id VARCHAR(50) NOT NULL UNIQUE,
    product_category_name VARCHAR(100),
    product_category_name_english VARCHAR(100),
    product_weight_g NUMERIC(10,2),
    product_length_cm NUMERIC(10,2),
    product_height_cm NUMERIC(10,2),
    product_width_cm NUMERIC(10,2),
    product_volume_cm3 NUMERIC(12,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_product_category ON dim_product(product_category_name_english);

-- 3. Dim Seller
CREATE TABLE dim_seller (
    seller_key SERIAL PRIMARY KEY,
    seller_id VARCHAR(50) NOT NULL UNIQUE,
    seller_zip_code_prefix VARCHAR(10),
    seller_city VARCHAR(100),
    seller_state CHAR(2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_seller_state ON dim_seller(seller_state);

-- 4. Dim Date (Date dimension for time analysis)
CREATE TABLE dim_date (
    date_key INTEGER PRIMARY KEY,
    full_date DATE NOT NULL,
    year INTEGER,
    quarter INTEGER,
    month INTEGER,
    month_name VARCHAR(20),
    week INTEGER,
    day_of_week INTEGER,
    day_name VARCHAR(20),
    is_weekend BOOLEAN,
    is_holiday BOOLEAN DEFAULT FALSE
);

-- 5. Dim Geolocation (Brazilian zip codes)
CREATE TABLE dim_geolocation (
    geolocation_key SERIAL PRIMARY KEY,
    zip_code_prefix VARCHAR(10),
    geolocation_lat NUMERIC(10,6),
    geolocation_lng NUMERIC(10,6),
    geolocation_city VARCHAR(100),
    geolocation_state CHAR(2)
);

CREATE INDEX idx_geo_zip ON dim_geolocation(zip_code_prefix);

-- =====================================================
-- FACT TABLE
-- =====================================================

-- Fact Orders (Grain: one row per order item)
CREATE TABLE fact_orders (
    order_fact_key SERIAL PRIMARY KEY,
    order_id VARCHAR(50) NOT NULL,
    order_item_id INTEGER NOT NULL,
    customer_key INTEGER NOT NULL REFERENCES dim_customer(customer_key),
    product_key INTEGER NOT NULL REFERENCES dim_product(product_key),
    seller_key INTEGER NOT NULL REFERENCES dim_seller(seller_key),
    date_key INTEGER NOT NULL REFERENCES dim_date(date_key),
    -- Order metrics
    price NUMERIC(10,2),
    freight_value NUMERIC(10,2),
    total_item_value NUMERIC(10,2),
    -- Timing metrics
    order_purchase_timestamp TIMESTAMP,
    order_delivered_timestamp TIMESTAMP,
    delivery_days INTEGER,
    delivery_delay INTEGER,
    is_late_delivery BOOLEAN,
    -- Review metrics
    review_score INTEGER,
    -- Payment metrics
    payment_type VARCHAR(50),
    payment_installments INTEGER,
    payment_value NUMERIC(10,2),
    -- Order status
    order_status VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uk_fact_orders_grain UNIQUE (order_id, order_item_id)
);

-- Indexes for fact table performance
CREATE INDEX idx_fact_customer ON fact_orders(customer_key);
CREATE INDEX idx_fact_product ON fact_orders(product_key);
CREATE INDEX idx_fact_date ON fact_orders(date_key);
CREATE INDEX idx_fact_order_id ON fact_orders(order_id);
CREATE INDEX idx_fact_delivery ON fact_orders(is_late_delivery);

-- =====================================================
-- POPULATE DATE DIMENSION (2016-2020)
-- =====================================================

INSERT INTO dim_date (date_key, full_date, year, quarter, month, month_name, week, day_of_week, day_name, is_weekend)
SELECT 
    TO_CHAR(d, 'YYYYMMDD')::INTEGER as date_key,
    d as full_date,
    EXTRACT(YEAR FROM d) as year,
    EXTRACT(QUARTER FROM d) as quarter,
    EXTRACT(MONTH FROM d) as month,
    TO_CHAR(d, 'FMMonth') as month_name,
    EXTRACT(WEEK FROM d) as week,
    EXTRACT(DOW FROM d) as day_of_week,
    TO_CHAR(d, 'FMDay') as day_name,
    CASE WHEN EXTRACT(DOW FROM d) IN (0, 6) THEN TRUE ELSE FALSE END as is_weekend
FROM generate_series('2016-01-01'::DATE, '2020-12-31'::DATE, '1 day'::INTERVAL) d;

-- =====================================================
-- BUSINESS VIEWS FOR ANALYTICS
-- =====================================================

-- 1. Order Status Summary
CREATE OR REPLACE VIEW v_order_status_summary AS
SELECT 
    order_status,
    COUNT(*) as order_count,
    SUM(total_item_value) as total_revenue,
    AVG(total_item_value) as avg_order_value
FROM fact_orders
GROUP BY order_status;

-- 2. Customer Lifetime Value (Current customers only)
CREATE OR REPLACE VIEW v_customer_lifetime_value AS
SELECT 
    c.customer_id,
    c.customer_unique_id,
    c.customer_city,
    c.customer_state,
    COUNT(f.order_id) as total_orders,
    SUM(f.total_item_value) as lifetime_value,
    AVG(f.total_item_value) as avg_order_value,
    MAX(f.order_purchase_timestamp) as last_purchase_date
FROM fact_orders f
JOIN dim_customer c ON f.customer_key = c.customer_key
WHERE c.is_current = TRUE
GROUP BY c.customer_id, c.customer_unique_id, c.customer_city, c.customer_state
ORDER BY lifetime_value DESC;

-- 3. Product Performance by Category
CREATE OR REPLACE VIEW v_product_category_performance AS
SELECT 
    p.product_category_name_english as category,
    COUNT(DISTINCT f.order_id) as total_orders,
    SUM(f.total_item_value) as total_revenue,
    AVG(f.review_score) as avg_review_score,
    SUM(f.total_item_value) / NULLIF(COUNT(DISTINCT f.order_id), 0) as revenue_per_order
FROM fact_orders f
JOIN dim_product p ON f.product_key = p.product_key
GROUP BY p.product_category_name_english
ORDER BY total_revenue DESC;

-- 4. Delivery Performance by State
CREATE OR REPLACE VIEW v_delivery_performance AS
SELECT 
    c.customer_state,
    COUNT(*) as total_orders,
    AVG(f.delivery_days) as avg_delivery_days,
    SUM(CASE WHEN f.is_late_delivery THEN 1 ELSE 0 END) as late_deliveries,
    (SUM(CASE WHEN f.is_late_delivery THEN 1 ELSE 0 END)::FLOAT / COUNT(*)) * 100 as late_delivery_pct
FROM fact_orders f
JOIN dim_customer c ON f.customer_key = c.customer_key
GROUP BY c.customer_state
ORDER BY late_delivery_pct DESC;