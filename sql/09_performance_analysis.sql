/* Analyze the monthly performance of products by comparing their sales
   to both the average sales performance of the product and
   the previous month's sales */

WITH monthly_performance AS (
    SELECT
        p.product_name,
        EXTRACT(MONTH FROM o.order_date) AS order_month,
        COALESCE(SUM(oi.total_value), 0) AS current_sales
    FROM products AS p
    LEFT JOIN order_items AS oi
        ON
            p.product_id = oi.product_id
    LEFT JOIN orders AS o
        ON
            oi.order_id = o.order_id
            AND o.order_date IS NOT NULL
    GROUP BY
        order_month,
        p.product_name
)

SELECT
    order_month,
    product_name,
    current_sales,
    ROUND(avg_sales, 2) AS avg_sales,
    CASE
        WHEN diff_avg > 0 THEN 'Above avg'
        WHEN diff_avg < 0 THEN 'Below avg'
        ELSE 'Avg'
    END AS avg_change,
    CASE
        WHEN diff_month > 0 THEN 'Increase'
        WHEN diff_month < 0 THEN 'Decrease'
        ELSE 'No change'
    END AS monthly_changes
FROM (
    SELECT
        order_month,
        product_name,
        current_sales,
        AVG(current_sales)
            OVER (PARTITION BY product_name) AS avg_sales,
        current_sales
        - AVG(current_sales) OVER (PARTITION BY product_name) AS diff_avg,
        LAG(current_sales)
            OVER (PARTITION BY product_name) AS py_month_sales,
        current_sales
        - LAG(current_sales) OVER (PARTITION BY product_name) AS diff_month
    FROM monthly_performance
) AS x
ORDER BY order_month ASC;
