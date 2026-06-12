-- Which categories contribute the most to overall sales?

WITH Grand AS(
    SELECT SUM(total_value) AS grand_revenue
    FROM order_items
),
Cate_revenue AS(
    SELECT
        C.category_name,
        SUM(OI.total_value) AS total_revenue
    FROM categories AS C
    LEFT JOIN products AS P ON
    C.category_id = P.category_id
    LEFT JOIN order_items AS OI ON
    OI.product_id = P.product_id
    GROUP BY C.category_name
)
SELECT
    CR.category_name,
    CR.total_revenue,
    ROUND(CR.total_revenue / G.grand_revenue * 100,2) AS pct_of_total
FROM Cate_revenue AS CR
CROSS JOIN Grand AS G
ORDER BY pct_of_total DESC;

