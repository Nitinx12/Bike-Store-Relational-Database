-- Analyse sales performance over time
-- Quick Date Functions
SELECT
    EXTRACT(YEAR FROM o.order_date) AS order_year,
    EXTRACT(MONTH FROM o.order_date) AS order_month,
    SUM(oi.total_value) AS total_revenue,
    COUNT(DISTINCT oi.order_id) AS total_orders,
    SUM(oi.quantity) AS total_quantity
FROM orders AS o
INNER JOIN order_items AS oi
    ON o.order_id = oi.order_id
WHERE o.order_date IS NOT NULL
GROUP BY order_year, order_month
ORDER BY order_year, order_month;

-- DATETRUNC()
SELECT
    DATE_TRUNC('month', o.order_date) AS order_month,
    SUM(oi.total_value) AS total_revenue,
    COUNT(DISTINCT oi.order_id) AS total_orders,
    SUM(oi.quantity) AS total_quantity
FROM orders AS o
INNER JOIN order_items AS oi
    ON o.order_id = oi.order_id
WHERE o.order_date IS NOT NULL
GROUP BY DATE_TRUNC('month', o.order_date)
ORDER BY DATE_TRUNC('month', o.order_date);

-- TO_CHAR()
SELECT
    TO_CHAR(o.order_date, 'YYYY-MM') AS order_month,
    SUM(oi.total_value) AS total_revenue,
    COUNT(DISTINCT oi.order_id) AS total_orders,
    SUM(oi.quantity) AS total_quantity
FROM orders AS o
INNER JOIN order_items AS oi
    ON o.order_id = oi.order_id
WHERE o.order_date IS NOT NULL
GROUP BY order_month
ORDER BY order_month ASC;
