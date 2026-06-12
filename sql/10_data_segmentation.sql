/*Segment products into cost ranges and 
count how many products fall into each segment*/

WITH Price_range AS(
    SELECT
        product_id,
        product_name,
        list_price,
        CASE
            WHEN list_price < 1000 THEN 'Below 1000'
            WHEN list_price BETWEEN 1000 AND 5000 THEN '1000-5000'
            WHEN list_price BETWEEN 5000 AND 10000 THEN '5000-10000'
            ELSE 'Above 10000'
        END AS price_range
    FROM products
)
SELECT
   price_range,
   COUNT(product_id) AS total_products
FROM Price_range
GROUP BY price_range
ORDER BY total_products ASC;

WITH Customer_spending AS(
    SELECT
        O.customer_id,
        SUM(OI.total_value) AS total_spending,
        MIN(O.order_date) AS first_order_date,
        MAX(O.order_date) AS last_order_date,
        (
        EXTRACT(YEAR FROM AGE(MAX(O.order_date),
        MIN(O.order_date))) * 12
        +
        EXTRACT(MONTH FROM AGE(MAX(O.order_date),
        MIN(O.order_date))) 
        ) AS lifespan_months
    FROM orders AS O
    INNER JOIN order_items AS OI ON
    OI.order_id = O.order_id
    GROUP BY O.customer_id
)
SELECT
    customer_segment,
    COUNT(customer_id) AS total_customers
FROM(
    SELECT
        customer_id,
        CASE
            WHEN lifespan_months >= 12 AND total_spending > 5000
                THEN 'VIP'
            WHEN lifespan_months >= 12 AND total_spending <= 5000
                THEN 'Regular'
            ELSE 'New'
        END AS customer_segment
    FROM Customer_spending
) AS X
GROUP BY customer_segment
ORDER BY total_customers DESC;


   
