SELECT
    'Total Sales' AS metric,
    ROUND(SUM(total_value), 2)::TEXT AS metric_value
FROM order_items

UNION ALL

SELECT
    'Total Quantity Sold' AS metric,
    SUM(quantity)::TEXT AS metric_value
FROM order_items

UNION ALL

SELECT
    'Average Selling Price' AS metric,
    ROUND(AVG(list_price), 2)::TEXT AS metric_value
FROM order_items

UNION ALL

SELECT
    'Total Orders' AS metric,
    COUNT(*)::TEXT AS metric_value
FROM orders

UNION ALL

SELECT
    'Total Products' AS metric,
    COUNT(*)::TEXT AS metric_value
FROM products

UNION ALL

SELECT
    'Total Customers' AS metric,
    COUNT(*)::TEXT AS metric_value
FROM customers

UNION ALL

SELECT
    'Customers With Orders' AS metric,
    COUNT(DISTINCT customer_id)::TEXT AS metric_value
FROM orders

UNION ALL

SELECT
    'Average Order Value' AS metric,
    ROUND(
        SUM(total_value)
        / COUNT(DISTINCT order_id),
        2
    )::TEXT AS metric_value
FROM order_items

UNION ALL

SELECT
    'Revenue Per Customer' AS metric,
    ROUND(
        SUM(oi.total_value)
        / COUNT(DISTINCT o.customer_id),
        2
    )::TEXT AS metric_value
FROM order_items AS oi
INNER JOIN orders AS o
    ON oi.order_id = o.order_id

UNION ALL

SELECT
    'Revenue Per Product' AS metric,
    ROUND(
        SUM(total_value)
        / COUNT(DISTINCT product_id),
        2
    )::TEXT AS metric_value
FROM order_items

UNION ALL

SELECT
    'Unique Products Sold' AS metric,
    COUNT(DISTINCT product_id)::TEXT AS metric_value
FROM order_items

UNION ALL

SELECT
    'Average Items Per Order' AS metric,
    ROUND(
        SUM(quantity)
        / COUNT(DISTINCT order_id),
        2
    )::TEXT AS metric_value
FROM order_items;
