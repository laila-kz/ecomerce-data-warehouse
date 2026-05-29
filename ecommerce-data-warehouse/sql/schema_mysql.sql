-- =====================================================
-- MySQL-compatible STAR SCHEMA FOR BRAZILIAN E-COMMERCE (OLIST)
-- Converted from Postgres schema.sql
-- =====================================================

CREATE DATABASE IF NOT EXISTS ecommerce_dw;
USE ecommerce_dw;

-- Drop existing tables (MySQL does not support CASCADE in DROP TABLE)
DROP TABLE IF EXISTS fact_orders;
DROP TABLE IF EXISTS dim_customer;
DROP TABLE IF EXISTS dim_product;
DROP TABLE IF EXISTS dim_seller;
DROP TABLE IF EXISTS dim_date;
DROP TABLE IF EXISTS dim_geolocation;

-- =====================================================
-- DIMENSION TABLES
-- =====================================================

-- 1. Dim Customer (SCD Type 2)
CREATE TABLE dim_customer (
    customer_key INT AUTO_INCREMENT PRIMARY KEY,
    customer_id VARCHAR(50) NOT NULL,
    customer_unique_id VARCHAR(50),
    customer_zip_code_prefix VARCHAR(10),
    customer_city VARCHAR(100),
    customer_state CHAR(2),
    -- SCD2 columns
    valid_from DATE NOT NULL DEFAULT (CURRENT_DATE()),
    valid_to DATE,
    is_current TINYINT(1) DEFAULT 1,
    version INTEGER DEFAULT 1,
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uk_customer_scd2 UNIQUE (customer_id, version)
)
ENGINE=InnoDB;

-- MySQL does not support partial indexes; create a normal index instead
CREATE INDEX idx_customer_current ON dim_customer(is_current);
CREATE INDEX idx_customer_city ON dim_customer(customer_city);
CREATE INDEX idx_customer_state ON dim_customer(customer_state);

-- 2. Dim Product
CREATE TABLE dim_product (
    product_key INT AUTO_INCREMENT PRIMARY KEY,
    product_id VARCHAR(50) NOT NULL UNIQUE,
    product_category_name VARCHAR(100),
    product_category_name_english VARCHAR(100),
    product_weight_g DECIMAL(10,2),
    product_length_cm DECIMAL(10,2),
    product_height_cm DECIMAL(10,2),
    product_width_cm DECIMAL(10,2),
    product_volume_cm3 DECIMAL(12,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
ENGINE=InnoDB;

CREATE INDEX idx_product_category ON dim_product(product_category_name_english);

-- 3. Dim Seller
CREATE TABLE dim_seller (
    seller_key INT AUTO_INCREMENT PRIMARY KEY,
    seller_id VARCHAR(50) NOT NULL UNIQUE,
    seller_zip_code_prefix VARCHAR(10),
    seller_city VARCHAR(100),
    seller_state CHAR(2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
ENGINE=InnoDB;

CREATE INDEX idx_seller_state ON dim_seller(seller_state);

-- 4. Dim Date (Date dimension for time analysis)
CREATE TABLE dim_date (
    date_key INT PRIMARY KEY,
    full_date DATE NOT NULL,
    year INTEGER,
    quarter INTEGER,
    month INTEGER,
    month_name VARCHAR(20),
    week INTEGER,
    day_of_week INTEGER,
    day_name VARCHAR(20),
    is_weekend TINYINT(1),
    is_holiday TINYINT(1) DEFAULT 0
)
ENGINE=InnoDB;

-- 5. Dim Geolocation (Brazilian zip codes)
CREATE TABLE dim_geolocation (
    geolocation_key INT AUTO_INCREMENT PRIMARY KEY,
    zip_code_prefix VARCHAR(10),
    geolocation_lat DECIMAL(10,6),
    geolocation_lng DECIMAL(10,6),
    geolocation_city VARCHAR(100),
    geolocation_state CHAR(2)
)
ENGINE=InnoDB;

CREATE INDEX idx_geo_zip ON dim_geolocation(zip_code_prefix);

-- =====================================================
-- FACT TABLE
-- =====================================================

-- Fact Orders (Grain: one row per order item)
CREATE TABLE fact_orders (
    order_fact_key INT AUTO_INCREMENT PRIMARY KEY,
    order_id VARCHAR(50) NOT NULL,
    order_item_id INTEGER NOT NULL,
    customer_key INTEGER NOT NULL,
    product_key INTEGER NOT NULL,
    seller_key INTEGER NOT NULL,
    date_key INTEGER NOT NULL,
    -- Order metrics
    price DECIMAL(10,2),
    freight_value DECIMAL(10,2),
    total_item_value DECIMAL(10,2),
    -- Timing metrics
    order_purchase_timestamp DATETIME,
    order_delivered_timestamp DATETIME,
    delivery_days INTEGER,
    delivery_delay INTEGER,
    is_late_delivery TINYINT(1),
    -- Review metrics
    review_score INTEGER,
    -- Payment metrics
    payment_type VARCHAR(50),
    payment_installments INTEGER,
    payment_value DECIMAL(10,2),
    -- Order status
    order_status VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uk_fact_orders_grain UNIQUE (order_id, order_item_id)
)
ENGINE=InnoDB;

-- Indexes for fact table performance
CREATE INDEX idx_fact_customer ON fact_orders(customer_key);
CREATE INDEX idx_fact_product ON fact_orders(product_key);
CREATE INDEX idx_fact_date ON fact_orders(date_key);
CREATE INDEX idx_fact_order_id ON fact_orders(order_id);
CREATE INDEX idx_fact_delivery ON fact_orders(is_late_delivery);

-- =====================================================
-- POPULATE DATE DIMENSION (2016-2020) using recursive CTE (MySQL 8+)
-- Adjust the date range as needed
SET SESSION cte_max_recursion_depth = 2000;

INSERT INTO dim_date (date_key, full_date, year, quarter, month, month_name, week, day_of_week, day_name, is_weekend)
WITH RECURSIVE seq AS (
  SELECT CAST('2016-01-01' AS DATE) AS d
  UNION ALL
  SELECT DATE_ADD(d, INTERVAL 1 DAY) FROM seq WHERE d < '2020-12-31'
)
SELECT
  CAST(DATE_FORMAT(d, '%Y%m%d') AS UNSIGNED) AS date_key,
  d AS full_date,
  YEAR(d) AS year,
  QUARTER(d) AS quarter,
  MONTH(d) AS month,
  DATE_FORMAT(d, '%M') AS month_name,
  WEEK(d, 3) AS week,
  DAYOFWEEK(d) - 1 AS day_of_week, -- convert to 0=Sunday..6=Saturday similar to Postgres
  DATE_FORMAT(d, '%W') AS day_name,
  CASE WHEN DAYOFWEEK(d) IN (1,7) THEN 1 ELSE 0 END AS is_weekend
FROM seq;

-- =====================================================
-- BUSINESS VIEWS FOR ANALYTICS (MySQL-compatible)
-- Note: MySQL supports CREATE OR REPLACE VIEW starting in 8.0.22; otherwise DROP+CREATE

DROP VIEW IF EXISTS v_order_status_summary;
CREATE VIEW v_order_status_summary AS
SELECT
  order_status,
  COUNT(*) AS order_count,
  SUM(total_item_value) AS total_revenue,
  AVG(total_item_value) AS avg_order_value
FROM fact_orders
GROUP BY order_status;

DROP VIEW IF EXISTS v_customer_lifetime_value;
CREATE VIEW v_customer_lifetime_value AS
SELECT
  c.customer_id,
  c.customer_unique_id,
  c.customer_city,
  c.customer_state,
  COUNT(f.order_id) AS total_orders,
  SUM(f.total_item_value) AS lifetime_value,
  AVG(f.total_item_value) AS avg_order_value,
  MAX(f.order_purchase_timestamp) AS last_purchase_date
FROM fact_orders f
JOIN dim_customer c ON f.customer_key = c.customer_key
WHERE c.is_current = 1
GROUP BY c.customer_id, c.customer_unique_id, c.customer_city, c.customer_state
ORDER BY lifetime_value DESC;

DROP VIEW IF EXISTS v_product_category_performance;
CREATE VIEW v_product_category_performance AS
SELECT
  p.product_category_name_english AS category,
  COUNT(DISTINCT f.order_id) AS total_orders,
  SUM(f.total_item_value) AS total_revenue,
  AVG(f.review_score) AS avg_review_score,
  SUM(f.total_item_value) / NULLIF(COUNT(DISTINCT f.order_id), 0) AS revenue_per_order
FROM fact_orders f
JOIN dim_product p ON f.product_key = p.product_key
GROUP BY p.product_category_name_english
ORDER BY total_revenue DESC;

DROP VIEW IF EXISTS v_delivery_performance;
CREATE VIEW v_delivery_performance AS
SELECT
  c.customer_state,
  COUNT(*) AS total_orders,
  AVG(f.delivery_days) AS avg_delivery_days,
  SUM(CASE WHEN f.is_late_delivery = 1 THEN 1 ELSE 0 END) AS late_deliveries,
  (SUM(CASE WHEN f.is_late_delivery = 1 THEN 1 ELSE 0 END) / COUNT(*)) * 100 AS late_delivery_pct
FROM fact_orders f
JOIN dim_customer c ON f.customer_key = c.customer_key
GROUP BY c.customer_state
ORDER BY late_delivery_pct DESC;
