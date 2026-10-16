-- Which 5 products Generating the Highest Revenue?
-- Simple Ranking
SELECT
    p.product_id,
    p.product_name,
    COALESCE(SUM(oi.total_value), 0) AS total_revenue
FROM products AS p
LEFT JOIN order_items AS oi
    ON p.product_id = oi.product_id
GROUP BY
    p.product_id,
    p.product_name
ORDER BY
    total_revenue DESC
LIMIT 5;

-- Complex but Flexibly Ranking Using Window Functions
SELECT
    x.product_id,
    x.product_name,
    x.total_revenue
FROM (
    SELECT
        p.product_id,
        p.product_name,
        COALESCE(SUM(oi.total_value), 0) AS total_revenue,
        DENSE_RANK()
            OVER (ORDER BY COALESCE(SUM(oi.total_value), 0) DESC) AS rnk
    FROM products AS p
    LEFT JOIN order_items AS oi
        ON p.product_id = oi.product_id
    GROUP BY
        p.product_id,
        p.product_name
    ORDER BY
        total_revenue DESC
) AS x
WHERE
    x.rnk <= 5;

-- What are the 5 worst-performing products in terms of sales?
SELECT
    p.product_id,
    p.product_name,
    COALESCE(SUM(oi.total_value), 0) AS total_revenue
FROM products AS p
LEFT JOIN order_items AS oi
    ON p.product_id = oi.product_id
GROUP BY
    p.product_id,
    p.product_name
ORDER BY
    total_revenue ASC
LIMIT 5;

-- Find the top 10 customers who have generated the highest revenue
SELECT
    x.customer_id,
    x.customer_name,
    x.total_revenue
FROM (
    SELECT
        c.customer_id,
        CONCAT(c.first_name, ' ', c.last_name) AS customer_name,
        SUM(oi.total_value) AS total_revenue,
        DENSE_RANK()
            OVER (ORDER BY SUM(oi.total_value) DESC) AS rnk
    FROM customers AS c
    LEFT JOIN orders AS o
        ON c.customer_id = o.customer_id
    LEFT JOIN order_items AS oi
        ON o.order_id = oi.order_id
    GROUP BY
        c.customer_id,
        customer_name
) AS x
WHERE
    x.rnk <= 10;

-- The 3 customers with the fewest orders placed
SELECT
    c.customer_id,
    CONCAT(c.first_name, ' ', c.last_name) AS full_name,
    COUNT(DISTINCT oi.order_id) AS total_orders
FROM customers AS c
LEFT JOIN orders AS o
    ON c.customer_id = o.customer_id
LEFT JOIN order_items AS oi
    ON o.order_id = oi.order_id
GROUP BY
    c.customer_id,
    full_name
ORDER BY
    total_orders ASC
LIMIT 3;
