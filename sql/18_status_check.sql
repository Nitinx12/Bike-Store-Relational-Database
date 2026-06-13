SELECT
    'Completed Orders' AS metric,
    COUNT(*) FILTER (WHERE order_status = 'Completed') AS value
FROM orders

UNION ALL

SELECT
    'Pending Orders',
    COUNT(*) FILTER (WHERE order_status = 'Pending')
FROM orders

UNION ALL

SELECT
    'Rejected Orders',
    COUNT(*) FILTER (WHERE order_status = 'Rejected')
FROM orders

UNION ALL

SELECT
    'Processing Orders',
    COUNT(*) FILTER (WHERE order_status = 'Processing')
FROM orders;