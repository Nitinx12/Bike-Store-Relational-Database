-- Analyse sales performance over time
-- Quick Date Functions
SELECT
    EXTRACT(YEAR FROM O.order_date) AS order_year,
    EXTRACT(MONTH FROM O.order_date) AS order_month,
    SUM(OI.total_value) AS total_revenue,
    COUNT(DISTINCT OI.order_id) AS total_orders,
    SUM(OI.quantity) AS total_quantity
FROM orders AS O
INNER JOIN order_items AS OI ON
OI.order_id = O.order_id
WHERE O.order_date IS NOT NULL
GROUP BY order_year, order_month
ORDER BY order_year, order_month;

-- DATETRUNC()
SELECT
    DATE_TRUNC('month', O.order_date) AS order_month,
    SUM(OI.total_value) AS total_revenue,
    COUNT(DISTINCT OI.order_id) AS total_orders,
    SUM(OI.quantity) AS total_quantity
FROM orders O
INNER JOIN order_items OI ON 
OI.order_id = O.order_id
WHERE O.order_date IS NOT NULL
GROUP BY DATE_TRUNC('month', O.order_date)
ORDER BY DATE_TRUNC('month', O.order_date);

-- TO_CHAR()
SELECT
    TO_CHAR(O.order_date,'YYYY-MM') AS order_month,
    SUM(OI.total_value) AS total_revenue,
    COUNT(DISTINCT OI.order_id) AS total_orders,
    SUM(OI.quantity) AS total_quantity
FROM orders O
INNER JOIN order_items OI ON 
OI.order_id = O.order_id
WHERE O.order_date IS NOT NULL
GROUP BY order_month
ORDER BY order_month ASC;

