-- =====================================================
-- ANALYTICS QUERIES FOR OLIST ECOMMERCE DATA WAREHOUSE
-- Business KPIs and performance metrics
-- =====================================================

-- 1. Overall Business KPIs
-- =====================================================
SELECT 
    COUNT(DISTINCT order_id) as total_orders,
    SUM(total_item_value) as total_revenue,
    AVG(total_item_value) as avg_order_value,
    COUNT(DISTINCT customer_key) as unique_customers,
    SUM(total_item_value) / NULLIF(COUNT(DISTINCT customer_key), 0) as revenue_per_customer,
    AVG(delivery_days) as avg_delivery_days,
    SUM(CASE WHEN is_late_delivery THEN 1 ELSE 0 END) as late_deliveries,
    (SUM(CASE WHEN is_late_delivery THEN 1 ELSE 0 END)::FLOAT / COUNT(*)) * 100 as late_delivery_pct
FROM fact_orders;

-- 2. Monthly Revenue Trend (Year-over-Year)
-- =====================================================
WITH monthly_revenue AS (
    SELECT 
        d.year,
        d.month,
        d.month_name,
        SUM(f.total_item_value) as revenue,
        COUNT(DISTINCT f.order_id) as order_count
    FROM fact_orders f
    JOIN dim_date d ON f.date_key = d.date_key
    GROUP BY d.year, d.month, d.month_name
)
SELECT 
    year,
    month_name,
    revenue,
    order_count,
    revenue / NULLIF(order_count, 0) as revenue_per_order,
    LAG(revenue) OVER (PARTITION BY month ORDER BY year) as prev_year_revenue,
    ((revenue - LAG(revenue) OVER (PARTITION BY month ORDER BY year)) / 
        NULLIF(LAG(revenue) OVER (PARTITION BY month ORDER BY year), 0)) * 100 as yoy_growth_pct
FROM monthly_revenue
ORDER BY year, month;

-- 3. Top 10 Products by Revenue
-- =====================================================
SELECT 
    p.product_category_name_english as category,
    p.product_id,
    COUNT(DISTINCT f.order_id) as order_count,
    SUM(f.total_item_value) as total_revenue,
    AVG(f.review_score) as avg_review_score,
    SUM(f.total_item_value) / NULLIF(COUNT(DISTINCT f.order_id), 0) as revenue_per_order
FROM fact_orders f
JOIN dim_product p ON f.product_key = p.product_key
WHERE p.product_category_name_english IS NOT NULL
GROUP BY p.product_category_name_english, p.product_id
ORDER BY total_revenue DESC
LIMIT 10;

-- 4. Customer Segmentation by Spending (RFM Analysis)
-- =====================================================
WITH customer_rfm AS (
    SELECT 
        c.customer_unique_id,
        c.customer_city,
        c.customer_state,
        COUNT(DISTINCT f.order_id) as frequency,
        SUM(f.total_item_value) as monetary,
        MAX(f.order_purchase_timestamp) as last_purchase_date,
        EXTRACT(DAY FROM (CURRENT_DATE - MAX(f.order_purchase_timestamp))) as recency
    FROM fact_orders f
    JOIN dim_customer c ON f.customer_key = c.customer_key
    WHERE c.is_current = TRUE
    GROUP BY c.customer_unique_id, c.customer_city, c.customer_state
),
rfm_scores AS (
    SELECT 
        *,
        NTILE(4) OVER (ORDER BY recency DESC) as recency_score,
        NTILE(4) OVER (ORDER BY frequency) as frequency_score,
        NTILE(4) OVER (ORDER BY monetary) as monetary_score
    FROM customer_rfm
)
SELECT 
    CASE 
        WHEN recency_score >= 3 AND frequency_score >= 3 AND monetary_score >= 3 THEN 'Champions'
        WHEN recency_score >= 3 AND frequency_score >= 2 THEN 'Loyal Customers'
        WHEN recency_score >= 2 AND monetary_score >= 2 THEN 'Potential Loyalists'
        WHEN recency_score >= 3 AND monetary_score <= 2 THEN 'New Customers'
        WHEN recency_score <= 2 AND monetary_score >= 3 THEN 'At Risk'
        ELSE 'Lost Customers'
    END as customer_segment,
    COUNT(*) as customer_count,
    AVG(monetary) as avg_spend,
    SUM(monetary) as total_revenue
FROM rfm_scores
GROUP BY customer_segment
ORDER BY total_revenue DESC;

-- 5. Delivery Performance Analysis by Region
-- =====================================================
SELECT 
    c.customer_state as state,
    COUNT(DISTINCT f.order_id) as total_orders,
    AVG(f.delivery_days) as avg_delivery_days,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY f.delivery_days) as median_delivery_days,
    MIN(f.delivery_days) as min_delivery_days,
    MAX(f.delivery_days) as max_delivery_days,
    SUM(CASE WHEN f.is_late_delivery THEN 1 ELSE 0 END) as late_deliveries,
    ROUND((SUM(CASE WHEN f.is_late_delivery THEN 1 ELSE 0 END)::FLOAT / COUNT(*)) * 100, 2) as late_delivery_pct,
    AVG(f.review_score) as avg_review_score
FROM fact_orders f
JOIN dim_customer c ON f.customer_key = c.customer_key
WHERE f.delivery_days IS NOT NULL
GROUP BY c.customer_state
ORDER BY late_delivery_pct DESC;

-- 6. Product Category Performance
-- =====================================================
SELECT 
    p.product_category_name_english as category,
    COUNT(DISTINCT f.order_id) as order_count,
    SUM(f.total_item_value) as revenue,
    SUM(f.freight_value) as total_freight,
    AVG(f.review_score) as avg_review_score,
    COUNT(DISTINCT f.seller_key) as unique_sellers,
    AVG(f.price) as avg_price,
    RANK() OVER (ORDER BY SUM(f.total_item_value) DESC) as revenue_rank
FROM fact_orders f
JOIN dim_product p ON f.product_key = p.product_key
WHERE p.product_category_name_english IS NOT NULL
GROUP BY p.product_category_name_english
ORDER BY revenue DESC;

-- 7. Payment Method Analysis
-- =====================================================
SELECT 
    payment_type,
    COUNT(DISTINCT order_id) as order_count,
    SUM(payment_value) as total_payment_value,
    AVG(payment_value) as avg_payment_value,
    AVG(payment_installments) as avg_installments,
    COUNT(DISTINCT customer_key) as unique_customers
FROM fact_orders
WHERE payment_type IS NOT NULL
GROUP BY payment_type
ORDER BY total_payment_value DESC;

-- 8. Customer Lifetime Value (Top 100)
-- =====================================================
SELECT 
    c.customer_unique_id,
    c.customer_city,
    c.customer_state,
    COUNT(f.order_id) as order_count,
    SUM(f.total_item_value) as lifetime_value,
    AVG(f.total_item_value) as avg_order_value,
    MIN(f.order_purchase_timestamp) as first_purchase,
    MAX(f.order_purchase_timestamp) as last_purchase,
    EXTRACT(DAY FROM (MAX(f.order_purchase_timestamp) - MIN(f.order_purchase_timestamp))) as customer_lifetime_days
FROM fact_orders f
JOIN dim_customer c ON f.customer_key = c.customer_key
WHERE c.is_current = TRUE
GROUP BY c.customer_unique_id, c.customer_city, c.customer_state
ORDER BY lifetime_value DESC
LIMIT 100;

-- 9. Seasonal Trends by Month
-- =====================================================
SELECT 
    d.month_name,
    d.year,
    COUNT(DISTINCT f.order_id) as order_count,
    SUM(f.total_item_value) as revenue,
    AVG(f.total_item_value) as avg_order_value,
    AVG(f.delivery_days) as avg_delivery_days,
    AVG(f.review_score) as avg_review_score
FROM fact_orders f
JOIN dim_date d ON f.date_key = d.date_key
GROUP BY d.year, d.month, d.month_name
ORDER BY d.year, d.month;

-- 10. Seller Performance Analysis
-- =====================================================
SELECT 
    s.seller_city,
    s.seller_state,
    COUNT(DISTINCT f.order_id) as total_orders,
    SUM(f.total_item_value) as total_revenue,
    AVG(f.review_score) as avg_review_score,
    AVG(f.delivery_days) as avg_delivery_days,
    COUNT(DISTINCT f.product_key) as unique_products_sold
FROM fact_orders f
JOIN dim_seller s ON f.seller_key = s.seller_key
GROUP BY s.seller_city, s.seller_state
HAVING COUNT(DISTINCT f.order_id) > 10
ORDER BY total_revenue DESC
LIMIT 20;

-- 11. Review Score Distribution by Delivery Performance
-- =====================================================
SELECT 
    f.review_score,
    COUNT(*) as review_count,
    AVG(f.delivery_days) as avg_delivery_days,
    AVG(f.total_item_value) as avg_order_value,
    SUM(CASE WHEN f.is_late_delivery THEN 1 ELSE 0 END) as late_delivery_count,
    ROUND(AVG(CASE WHEN f.is_late_delivery THEN 1 ELSE 0 END) * 100, 2) as late_delivery_pct
FROM fact_orders f
WHERE f.review_score IS NOT NULL
GROUP BY f.review_score
ORDER BY f.review_score DESC;

-- 12. Hourly Order Patterns (if timestamp available)
-- =====================================================
SELECT 
    EXTRACT(HOUR FROM order_purchase_timestamp) as hour_of_day,
    COUNT(*) as order_count,
    AVG(total_item_value) as avg_order_value
FROM fact_orders
WHERE order_purchase_timestamp IS NOT NULL
GROUP BY EXTRACT(HOUR FROM order_purchase_timestamp)
ORDER BY hour_of_day;

-- 13. Cross-Selling Opportunities (Products bought together)
-- =====================================================
WITH order_pairs AS (
    SELECT 
        f1.order_id,
        f1.product_key as product1,
        f2.product_key as product2
    FROM fact_orders f1
    JOIN fact_orders f2 ON f1.order_id = f2.order_id 
        AND f1.product_key < f2.product_key
)
SELECT 
    p1.product_category_name_english as category1,
    p2.product_category_name_english as category2,
    COUNT(*) as times_bought_together
FROM order_pairs op
JOIN dim_product p1 ON op.product1 = p1.product_key
JOIN dim_product p2 ON op.product2 = p2.product_key
GROUP BY p1.product_category_name_english, p2.product_category_name_english
HAVING COUNT(*) > 10
ORDER BY times_bought_together DESC
LIMIT 20;

-- 14. SCD2 Change Tracking (Customer history example)
-- =====================================================
SELECT 
    customer_id,
    customer_unique_id,
    customer_city,
    customer_state,
    valid_from,
    valid_to,
    is_current,
    version,
    CASE 
        WHEN version = 1 AND is_current = FALSE THEN 'Original - Changed'
        WHEN is_current = TRUE AND version > 1 THEN 'Current Version'
        WHEN is_current = FALSE AND version > 1 THEN 'Historical Version'
        ELSE 'Current Original'
    END as change_type
FROM dim_customer
WHERE customer_unique_id IN (
    SELECT customer_unique_id 
    FROM dim_customer 
    GROUP BY customer_unique_id 
    HAVING COUNT(*) > 1
)
ORDER BY customer_unique_id, version;

-- 15. Executive Dashboard Summary
-- =====================================================
SELECT 
    'Total Revenue' as metric_name,
    TO_CHAR(SUM(total_item_value), 'FM$999,999,999.00') as value,
    TO_CHAR(SUM(total_item_value) / NULLIF(COUNT(DISTINCT date_part('year', order_purchase_timestamp)), 0), 'FM$999,999,999.00') as avg_per_year
FROM fact_orders
UNION ALL
SELECT 
    'Total Orders',
    TO_CHAR(COUNT(DISTINCT order_id), 'FM999,999,999'),
    TO_CHAR(COUNT(DISTINCT order_id) / NULLIF(COUNT(DISTINCT date_part('year', order_purchase_timestamp)), 0), 'FM999,999')
FROM fact_orders
UNION ALL
SELECT 
    'Avg Order Value',
    TO_CHAR(AVG(total_item_value), 'FM$999,999.00'),
    TO_CHAR(AVG(total_item_value), 'FM$999,999.00')
FROM fact_orders
UNION ALL
SELECT 
    'Unique Customers',
    TO_CHAR(COUNT(DISTINCT customer_key), 'FM999,999,999'),
    TO_CHAR(COUNT(DISTINCT customer_key) / NULLIF(COUNT(DISTINCT date_part('year', order_purchase_timestamp)), 0), 'FM999,999')
FROM fact_orders
UNION ALL
SELECT 
    'Avg Delivery Days',
    TO_CHAR(AVG(delivery_days), 'FM999.0'),
    TO_CHAR(AVG(delivery_days), 'FM999.0')
FROM fact_orders
WHERE delivery_days IS NOT NULL
UNION ALL
SELECT 
    'On-Time Delivery %',
    TO_CHAR((1 - SUM(CASE WHEN is_late_delivery THEN 1 ELSE 0 END)::FLOAT / COUNT(*)) * 100, 'FM999.0') || '%',
    TO_CHAR((1 - SUM(CASE WHEN is_late_delivery THEN 1 ELSE 0 END)::FLOAT / COUNT(*)) * 100, 'FM999.0') || '%'
FROM fact_orders;