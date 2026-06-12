-- Calculate the total sales per month 
-- and the running total of sales over time
SELECT
    order_month,
    total_sales,
    SUM(total_sales)
        OVER(ORDER BY order_month ASC) AS running_total_sales,
    ROUND(AVG(avg_price)
        OVER(ORDER BY order_month ASC),2) AS avg_price
FROM(
    SELECT
        TO_CHAR(O.order_date,'YYYY-MM') AS order_month,
        SUM(OI.total_value) AS total_sales,
        ROUND(AVG(OI.list_price),2) AS avg_price
    FROM orders AS O
    INNER JOIN order_items AS OI ON
    OI.order_id = O.order_id
    WHERE O.order_date IS NOT NULL
    GROUP BY order_month
) AS X;

