-- Detailed Product Report
WITH Product_metric AS(
    SELECT
        P.product_id,
        P.product_name,
        C.category_name,
        B.brand_name,
        COALESCE(ROUND(SUM(OI.total_value),2),0) AS total_revenue,
        COALESCE(SUM(OI.quantity),0) AS total_quantity,
        COUNT(DISTINCT OI.order_id) AS total_orders,
        ROUND(AVG(OI.list_price),2) AS avg_price,
        COALESCE(SUM(OI.discount),2) AS total_discount,
        MIN(O.order_date) AS first_sale_date,
        MAX(O.order_date) AS last_sale_date
    FROM products AS P
    LEFT JOIN categories AS C ON
    C.category_id = P.category_id
    LEFT JOIN brands AS B ON
    B.brand_id = P.brand_id
    LEFT JOIN order_items AS OI ON
    OI.product_id = P.product_id
    LEFT JOIN orders AS O ON
    OI.order_id = O.order_id
    GROUP BY
        P.product_id, P.product_name,
        C.category_name, B.brand_name
),
Grand_total AS(
    SELECT SUM(OI.total_value) AS grand_revenue
    FROM order_items AS OI
),
Ranked AS(
    SELECT
        PB.*,
        GT.grand_revenue,
        ROUND(PB.total_revenue / NULLIF(PB.total_orders,0),2) AS avg_order_value,
        ROUND(PB.total_revenue / NULLIF(PB.total_quantity,0),2) AS revenue_per_units,
        ROUND(PB.total_revenue / NULLIF(PB.total_orders,0),2) AS avg_units_per_orders,
        CURRENT_DATE - PB.last_sale_date AS days_since_last_sale,
        ROUND(PB.total_revenue / GT.grand_revenue * 100,2) AS revenue_share_pct,
        ROUND((
                PB.total_revenue /
                NULLIF(SUM(PB.total_revenue) OVER (
                    PARTITION BY PB.category_name), 0) * 100
            )::numeric, 2) AS category_revenue_share_pct,
        DENSE_RANK()
            OVER(ORDER BY PB.total_revenue DESC) AS rank_overall,
        DENSE_RANK()
            OVER(PARTITION BY PB.category_name
            ORDER BY PB.total_revenue DESC) AS rank_in_category,
        DENSE_RANK()
            OVER(PARTITION BY PB.brand_name
            ORDER BY PB.total_revenue DESC) AS rank_in_brand,
        ROUND((
                SUM(PB.total_revenue) OVER (
                    ORDER BY PB.total_revenue DESC
                    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
                / NULLIF(GT.grand_revenue, 0) * 100
            )::numeric, 2) AS cumulative_revenue_pct
    FROM Product_metric AS PB
    CROSS JOIN Grand_total AS GT
)
SELECT *
FROM Ranked
ORDER BY rank_overall, rank_in_category, rank_in_brand ASC;