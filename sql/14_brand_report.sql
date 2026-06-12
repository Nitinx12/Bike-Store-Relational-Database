WITH Product_metric AS(
    SELECT
        B.brand_id,
        B.brand_name,
        COUNT(DISTINCT P.product_id) AS total_products,
        COUNT(DISTINCT OI.order_id) AS total_orders,
        COUNT(DISTINCT O.customer_id) AS unique_customers,
        COALESCE(ROUND(SUM(OI.total_value),2),0) AS total_revenue,
        COALESCE(ROUND(AVG(OI.total_value),2),0) AS avg_order_value,
        COALESCE(SUM(OI.quantity),0) AS units_sold
    FROM brands AS B
    LEFT JOIN products AS P ON
    P.brand_id = B.brand_id
    LEFT JOIN order_items AS OI ON
    OI.product_id = P.product_id
    LEFT JOIN orders AS O ON
    OI.order_id = O.order_id
    GROUP BY
        B.brand_id,
        B.brand_name
),
Grand_revenue AS(
    SELECT SUM(total_revenue) AS grand_revenue
    FROM Product_metric
)
SELECT
    RANK()
        OVER(ORDER BY PM.total_revenue DESC) AS brand_rank,
    PM.brand_id,
    PM.brand_name,
    PM.total_products,
    PM.units_sold,
    PM.unique_customers,
    PM.total_orders,
    PM.total_revenue,
    PM.avg_order_value,
    ROUND(PM.total_revenue / NULLIF(GR.grand_revenue,0) * 100,2) AS pct_of_total
FROM Product_metric AS PM
CROSS JOIN Grand_revenue AS GR
ORDER BY brand_rank ASC;