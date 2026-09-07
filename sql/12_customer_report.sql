-- Detailed Customer Report

WITH customer_metrics AS (
    SELECT
        c.customer_id,
        c.city,
        c.state,
        CONCAT(c.first_name, ' ', c.last_name) AS customer_name,
        COUNT(DISTINCT o.order_id) AS total_orders,
        COALESCE(SUM(oi.quantity), 0) AS total_items_purchased,
        COALESCE(SUM(oi.total_value), 0) AS lifetime_value,
        COALESCE(
            ROUND(
                SUM(oi.total_value)::numeric
                / NULLIF(COUNT(DISTINCT o.order_id), 0),
                2
            ),
            0
        ) AS avg_order_value,
        MIN(o.order_date) AS first_order,
        MAX(o.order_date) AS last_order,
        CASE
            WHEN MAX(o.order_date) IS NULL THEN NULL
            ELSE CURRENT_DATE - MAX(o.order_date)
        END AS days_since_last_order,
        CASE
            WHEN MIN(o.order_date) IS NULL THEN NULL
            ELSE CURRENT_DATE - MIN(o.order_date)
        END AS customer_tenure_days
    FROM customers AS c
    LEFT JOIN orders AS o
        ON
            c.customer_id = o.customer_id
    LEFT JOIN order_items AS oi
        ON
            o.order_id = oi.order_id
    GROUP BY
        c.customer_id,
        c.first_name,
        c.last_name,
        c.city,
        c.state
),

rfm_scores AS (
    SELECT
        *,
        NTILE(5) OVER (
            ORDER BY days_since_last_order DESC NULLS FIRST
        ) AS recency_score,
        NTILE(5) OVER (
            ORDER BY total_orders ASC
        ) AS frequency_score,
        NTILE(5) OVER (
            ORDER BY lifetime_value ASC
        ) AS monetary_score
    FROM customer_metrics
),

customer_analytics AS (
    SELECT
        r.*,
        (
            r.recency_score
            + r.frequency_score
            + r.monetary_score
        ) AS rfm_total,
        ROUND(
            100.0 * r.lifetime_value
            / NULLIF(SUM(r.lifetime_value) OVER (), 0),
            2
        ) AS revenue_contribution_pct,
        ROUND(
            (
                r.total_orders::numeric
                / NULLIF(r.customer_tenure_days, 0)
            ) * 30,
            2
        ) AS orders_per_month,
        CASE
            WHEN r.customer_tenure_days >= 90
                THEN
                    ROUND(
                        r.avg_order_value
                        * (
                            (
                                r.total_orders::numeric
                                / NULLIF(r.customer_tenure_days, 0)
                            ) * 365
                        ),
                        2
                    )
            ELSE 0
        END AS projected_annual_clv,
        CASE
            WHEN r.days_since_last_order IS NULL THEN 'No Orders'
            WHEN r.days_since_last_order <= 30 THEN 'Active'
            WHEN r.days_since_last_order <= 90 THEN 'At Risk'
            WHEN r.days_since_last_order <= 180 THEN 'Churning'
            ELSE 'Churned'
        END AS churn_status,
        CASE
            WHEN
                (r.recency_score + r.frequency_score + r.monetary_score) >= 13
                THEN 'Champions'
            WHEN
                (r.recency_score + r.frequency_score + r.monetary_score) >= 10
                THEN 'Loyal Customers'
            WHEN
                (r.recency_score + r.frequency_score + r.monetary_score) >= 7
                THEN 'Potential Loyalists'
            WHEN
                (r.recency_score + r.frequency_score + r.monetary_score) >= 4
                THEN 'At Risk'
            ELSE 'Lost Customers'
        END AS customer_segment
    FROM rfm_scores AS r
)

SELECT *
FROM customer_analytics
ORDER BY lifetime_value DESC;
