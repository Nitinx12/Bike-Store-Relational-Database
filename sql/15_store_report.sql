WITH Store_metric AS(
    SELECT
        S.store_id,
        S.store_name,
        S.city,
        S.state,
        COUNT(DISTINCT OI.order_id) AS total_orders,
        COUNT(DISTINCT OI.product_id) AS total_products,
        SUM(OI.quantity) AS total_quantity,
        COUNT(DISTINCT O.customer_id) AS unique_customers,
        SUM(OI.discount) AS total_discount,
        SUM(OI.total_value) AS total_revenue,
        SUM(oi.total_value) / NULLIF(COUNT(DISTINCT o.order_id),0) AS avg_order_value
    FROM stores AS S
    LEFT JOIN orders AS O ON
    S.store_id = O.store_id
    LEFT JOIN order_items AS OI ON
    OI.order_id = O.order_id
    GROUP BY
        S.store_id, S.store_name,
        S.city, S.state
),
Stock_check AS(
    SELECT
        store_id,
        SUM(quantity) AS total_stock
    FROM stocks
    GROUP BY store_id
),
Grand_revenue AS(
    SELECT
        SUM(OI.total_value) AS grand_revenue
    FROM order_items AS OI
)
SELECT
    RANK()
        OVER(ORDER BY SM.total_revenue DESC) AS store_rank,
    SM.store_id,
    SM.store_name,
    SM.city,
    SM.state,
    SM.total_orders,
    SM.total_products,
    SM.unique_customers,
    SM.total_quantity,
    SC.total_stock,
    SM.total_discount,
    SM.total_revenue,
    ROUND(avg_order_value,2) AS avg_order_value,
    ROUND(SM.total_revenue / NULLIF(GR.grand_revenue,0) * 100,2) AS pct_of_total
FROM Store_metric AS SM
LEFT JOIN Stock_check AS SC ON
SM.store_id = SC.store_id
CROSS JOIN Grand_revenue AS GR