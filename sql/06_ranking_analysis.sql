-- Which 5 products Generating the Highest Revenue?
-- Simple Ranking
SELECT
    P.product_id,
    P.product_name,
    COALESCE(SUM(OI.total_value),0) AS total_revenue
FROM products AS P
LEFT JOIN order_items AS OI ON
OI.product_id = P.product_id
GROUP BY P.product_id, P.product_name
ORDER BY total_revenue DESC
LIMIT 5;

-- Complex but Flexibly Ranking Using Window Functions
SELECT
    product_id,
    product_name,
    total_revenue
FROM(
    SELECT
        P.product_id,
        P.product_name,
        COALESCE(SUM(OI.total_value),0)  AS total_revenue,
        DENSE_RANK()
            OVER(ORDER BY COALESCE(SUM(OI.total_value),0) DESC) AS rnk
    FROM products AS P
    LEFT JOIN order_items AS OI ON
    OI.product_id = P.product_id
    GROUP BY P.product_id, P.product_name
    ORDER BY total_revenue DESC
) AS X
WHERE X.rnk <= 5;

-- What are the 5 worst-performing products in terms of sales?
SELECT
    P.product_id,
    P.product_name,
    COALESCE(SUM(OI.total_value),0) AS total_revenue
FROM products AS P
LEFT JOIN order_items AS OI ON
OI.product_id = P.product_id
GROUP BY P.product_id, P.product_name
ORDER BY total_revenue ASC
LIMIT 5;

-- Find the top 10 customers who have generated the highest revenue
SELECT
    customer_id,
    customer_name,
    total_revenue
FROM(
    SELECT
        C.customer_id,
        CONCAT(C.first_name,' ',C.last_name) AS customer_name,
        SUM(OI.total_value) AS total_revenue,
        DENSE_RANK()
            OVER(ORDER BY SUM(OI.total_value) DESC) AS rnk
    FROM customers AS C
    LEFT JOIN orders AS O ON
    C.customer_id = O.customer_id
    LEFT JOIN order_items AS OI ON
    OI.order_id = O.order_id
    GROUP BY C.customer_id, customer_name
) AS X
WHERE X.rnk <= 10;

-- The 3 customers with the fewest orders placed
SELECT
    C.customer_id,
    CONCAT(C.first_name,' ',C.last_name) AS full_name,
    COUNT(DISTINCT OI.order_id) AS total_orders
FROM customers AS C
LEFT JOIN orders AS O ON
C.customer_id = O.customer_id
LEFT JOIN order_items AS OI ON
OI.order_id = O.order_id
GROUP BY
    C.customer_id,
    full_name
ORDER BY total_orders ASC
LIMIT 3;