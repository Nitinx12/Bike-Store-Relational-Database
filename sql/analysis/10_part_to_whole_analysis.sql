-- Which categories contribute the most to overall sales?

WITH grand AS (
    SELECT
        SUM(total_value) AS grand_revenue
    FROM
        order_items
),

cate_revenue AS (
    SELECT
        c.category_name,
        SUM(oi.total_value) AS total_revenue
    FROM categories AS c
    LEFT JOIN products AS p
        ON c.category_id = p.category_id
    LEFT JOIN order_items AS oi
        ON p.product_id = oi.product_id
    GROUP BY
        c.category_name
)

SELECT
    cr.category_name,
    cr.total_revenue,
    ROUND(cr.total_revenue / g.grand_revenue * 100, 2) AS pct_of_total
FROM cate_revenue AS cr
CROSS JOIN grand AS g
ORDER BY
    pct_of_total DESC;
