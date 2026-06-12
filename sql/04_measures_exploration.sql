
SELECT 'Total Sales' AS metric,
       ROUND(SUM(total_value),2)::TEXT AS value
FROM order_items

UNION ALL

SELECT 'Total Quantity Sold',
       SUM(quantity)::TEXT
FROM order_items

UNION ALL

SELECT 'Average Selling Price',
       ROUND(AVG(list_price),2)::TEXT
FROM order_items

UNION ALL

SELECT 'Total Orders',
       COUNT(*)::TEXT
FROM orders

UNION ALL

SELECT 'Total Products',
       COUNT(*)::TEXT
FROM products

UNION ALL

SELECT 'Total Customers',
       COUNT(*)::TEXT
FROM customers

UNION ALL

SELECT 'Customers With Orders',
       COUNT(DISTINCT customer_id)::TEXT
FROM orders

UNION ALL

SELECT 'Average Order Value',
       ROUND(
           SUM(total_value) /
           COUNT(DISTINCT order_id)
       ,2)::TEXT
FROM order_items

UNION ALL

SELECT 'Revenue Per Customer',
       ROUND(
           SUM(oi.total_value) /
           COUNT(DISTINCT o.customer_id)
       ,2)::TEXT
FROM order_items oi
JOIN orders o
ON oi.order_id = o.order_id

UNION ALL

SELECT 'Revenue Per Product',
       ROUND(
           SUM(total_value) /
           COUNT(DISTINCT product_id)
       ,2)::TEXT
FROM order_items

UNION ALL

SELECT 'Unique Products Sold',
       COUNT(DISTINCT product_id)::TEXT
FROM order_items

UNION ALL

SELECT 'Average Items Per Order',
       ROUND(
           SUM(quantity) /
           COUNT(DISTINCT order_id)
       ,2)::TEXT
FROM order_items;