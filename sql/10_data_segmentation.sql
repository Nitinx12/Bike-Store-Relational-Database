/*Segment products into cost ranges and
count how many products fall into each segment*/

WITH Price_range AS (
    SELECT
        Product_id,
        Product_name,
        List_price,
        CASE
            WHEN List_price < 1000 THEN 'Below 1000'
            WHEN List_price BETWEEN 1000 AND 5000 THEN '1000-5000'
            WHEN List_price BETWEEN 5000 AND 10000 THEN '5000-10000'
            ELSE 'Above 10000'
        END AS Price_range
    FROM Products
)

SELECT
    Price_range,
    COUNT(Product_id) AS Total_products
FROM Price_range
GROUP BY Price_range
ORDER BY Total_products ASC;

WITH Customer_spending AS (
    SELECT
        O.Customer_id,
        SUM(Oi.Total_value) AS Total_spending,
        MIN(O.Order_date) AS First_order_date,
        MAX(O.Order_date) AS Last_order_date,
        (
            EXTRACT(YEAR FROM AGE(
                MAX(O.Order_date),
                MIN(O.Order_date)
            )) * 12
            +
            EXTRACT(MONTH FROM AGE(
                MAX(O.Order_date),
                MIN(O.Order_date)
            ))
        ) AS Lifespan_months
    FROM Orders AS O
    INNER JOIN Order_items AS Oi
        ON
            O.Order_id = Oi.Order_id
    GROUP BY O.Customer_id
)

SELECT
    Customer_segment,
    COUNT(Customer_id) AS Total_customers
FROM (
    SELECT
        Customer_id,
        CASE
            WHEN Lifespan_months >= 12 AND Total_spending > 5000
                THEN 'VIP'
            WHEN Lifespan_months >= 12 AND Total_spending <= 5000
                THEN 'Regular'
            ELSE 'New'
        END AS Customer_segment
    FROM Customer_spending
) AS X
GROUP BY Customer_segment
ORDER BY Total_customers DESC;
