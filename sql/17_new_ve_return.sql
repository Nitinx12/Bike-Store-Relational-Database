
WITH customer_first_purchase AS (
    SELECT
        customer_id,
        DATE_TRUNC('month', MIN(order_date)) AS first_purchase_month
    FROM orders
    WHERE order_status = 'Completed'
    GROUP BY customer_id
),
monthly_sales AS (
    SELECT
        DATE_TRUNC('month', o.order_date) AS month,
        o.customer_id,
        o.order_id,
        SUM(oi.total_value) AS order_revenue,
        SUM(oi.quantity) AS items_sold
    FROM orders o
    INNER JOIN order_items oi ON 
    o.order_id = oi.order_id
    WHERE o.order_status = 'Completed'
    GROUP BY
        DATE_TRUNC('month', o.order_date),
        o.customer_id,
        o.order_id
),

customer_segments AS (
    SELECT
        ms.month,
        ms.customer_id,
        CASE
            WHEN cfp.first_purchase_month = ms.month
            THEN 'New'
            ELSE 'Repeat'
        END AS customer_segment
    FROM monthly_sales ms
    INNER JOIN customer_first_purchase cfp
        ON ms.customer_id = cfp.customer_id
)
SELECT
    ms.month,
    COUNT(DISTINCT ms.order_id) AS total_orders,
    COUNT(DISTINCT ms.customer_id) AS total_customers,
    COUNT(DISTINCT CASE
        WHEN cs.customer_segment = 'New'
        THEN ms.customer_id
    END) AS new_customers,
    COUNT(DISTINCT CASE
        WHEN cs.customer_segment = 'Repeat'
        THEN ms.customer_id
    END) AS repeat_customers,
    SUM(ms.order_revenue) AS total_revenue,
    SUM(ms.items_sold) AS total_items_sold,
    ROUND(
        SUM(ms.order_revenue)::numeric
        / COUNT(DISTINCT ms.order_id),
        2
    ) AS avg_order_value,
    ROUND(
        SUM(ms.order_revenue)::numeric
        / COUNT(DISTINCT ms.customer_id),
        2
    ) AS revenue_per_customer
FROM monthly_sales ms
INNER JOIN customer_segments cs
    ON ms.month = cs.month
   AND ms.customer_id = cs.customer_id
GROUP BY ms.month
ORDER BY ms.month;