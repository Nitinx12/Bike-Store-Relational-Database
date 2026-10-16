SELECT
    'Completed Orders' AS metric,
    COUNT(*) FILTER (WHERE order_status = 'Completed') AS metric_value
FROM orders

UNION ALL

SELECT
    'Pending Orders' AS metric,
    COUNT(*) FILTER (WHERE order_status = 'Pending') AS metric_value
FROM orders

UNION ALL

SELECT
    'Rejected Orders' AS metric,
    COUNT(*) FILTER (WHERE order_status = 'Rejected') AS metric_value
FROM orders

UNION ALL

SELECT
    'Processing Orders' AS metric,
    COUNT(*) FILTER (WHERE order_status = 'Processing') AS metric_value
FROM orders;
