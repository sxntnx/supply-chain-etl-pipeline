-- ===========================================================================
-- Supply Chain Analytics — example queries against the star schema.
--
-- These are the questions the pipeline was built to answer. They double as a
-- smoke test: every query should return rows against database/supply_chain.db.
-- Run with:  sqlite3 database/supply_chain.db < sql/analytics_queries.sql
-- ===========================================================================

-- 1. On-Time Delivery (OTD) — the headline supply-chain KPI.
--    What share of order lines shipped late?
SELECT
    COUNT(*)                                            AS total_order_lines,
    SUM(is_late_delivery)                               AS late_order_lines,
    ROUND(100.0 * SUM(is_late_delivery) / COUNT(*), 1)  AS late_delivery_pct
FROM fact_orders;


-- 2. Average delivery delay by shipping mode.
--    Which service levels are actually meeting their promise?
SELECT
    shipping_mode,
    COUNT(*)                              AS order_lines,
    ROUND(AVG(delivery_delay_days), 2)    AS avg_delay_days,
    ROUND(100.0 * AVG(is_late_delivery), 1) AS late_pct
FROM fact_orders
GROUP BY shipping_mode
ORDER BY late_pct DESC;


-- 3. Profitability by region — revenue vs. margin.
--    Where are we selling at a loss?
SELECT
    order_region,
    ROUND(SUM(sales), 0)                          AS total_sales,
    ROUND(SUM(order_profit), 0)                   AS total_profit,
    ROUND(100.0 * SUM(order_profit) / SUM(sales), 1) AS margin_pct
FROM fact_orders
GROUP BY order_region
ORDER BY total_profit ASC;


-- 4. Top 10 products by revenue, with their margin.
SELECT
    p.product_name,
    p.category,
    ROUND(SUM(f.sales), 0)        AS revenue,
    ROUND(SUM(f.order_profit), 0) AS profit
FROM fact_orders f
JOIN dim_products p ON p.product_id = f.product_id
GROUP BY p.product_id
ORDER BY revenue DESC
LIMIT 10;


-- 5. Late-delivery rate by customer segment.
--    Is service quality uneven across our customer base?
SELECT
    c.segment,
    COUNT(*)                                 AS order_lines,
    ROUND(100.0 * AVG(f.is_late_delivery), 1) AS late_pct
FROM fact_orders f
JOIN dim_customers c ON c.customer_id = f.order_customer_id
GROUP BY c.segment
ORDER BY late_pct DESC;
