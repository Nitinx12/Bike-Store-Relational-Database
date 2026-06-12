-- Detailed Customer Report

WITH customer_metrics AS (
    SELECT
        C.customer_id,
        CONCAT(C.first_name, ' ', C.last_name) AS customer_name,
        C.city,
        C.state,
        COUNT(DISTINCT O.order_id) AS total_orders,
        COALESCE(SUM(OI.quantity), 0) AS total_items_purchased,
        COALESCE(SUM(OI.total_value), 0) AS lifetime_value,
        COALESCE(
            ROUND(
                SUM(OI.total_value)::numeric / NULLIF(COUNT(DISTINCT O.order_id), 0),
                2
            ),
            0
        ) AS avg_order_value,
        MIN(O.order_date) AS first_order,
        MAX(O.order_date) AS last_order,
        CASE
            WHEN MAX(O.order_date) IS NULL THEN NULL
            ELSE CURRENT_DATE - MAX(O.order_date)
        END AS days_since_last_order,
        CASE
            WHEN MIN(O.order_date) IS NULL THEN NULL
            ELSE CURRENT_DATE - MIN(O.order_date)
        END AS customer_tenure_days
    FROM customers AS C
    LEFT JOIN orders AS O ON 
    C.customer_id = O.customer_id
    LEFT JOIN order_items AS OI ON 
    O.order_id = OI.order_id
    GROUP BY
        C.customer_id,
        C.first_name,
        C.last_name,
        C.city,
        C.state
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
        R.*,
        (
            R.recency_score +
            R.frequency_score +
            R.monetary_score
        ) AS rfm_total,
        ROUND(
            100.0 * R.lifetime_value /
            NULLIF(SUM(R.lifetime_value) OVER (), 0),
            2
        ) AS revenue_contribution_pct,
        ROUND(
            (
                R.total_orders::numeric /
                NULLIF(R.customer_tenure_days, 0)
            ) * 30,
            2
        ) AS orders_per_month,
        CASE
            WHEN R.customer_tenure_days >= 90 THEN
                ROUND(
                    R.avg_order_value *
                    (
                        (
                            R.total_orders::numeric /
                            NULLIF(R.customer_tenure_days, 0)
                        ) * 365
                    ),
                    2
                )
            ELSE 0
        END AS projected_annual_clv,
        CASE
            WHEN R.days_since_last_order IS NULL THEN 'No Orders'
            WHEN R.days_since_last_order <= 30   THEN 'Active'
            WHEN R.days_since_last_order <= 90   THEN 'At Risk'
            WHEN R.days_since_last_order <= 180  THEN 'Churning'
            ELSE 'Churned'
        END AS churn_status,
        CASE
            WHEN (R.recency_score + R.frequency_score + R.monetary_score) >= 13 THEN 'Champions'
            WHEN (R.recency_score + R.frequency_score + R.monetary_score) >= 10 THEN 'Loyal Customers'
            WHEN (R.recency_score + R.frequency_score + R.monetary_score) >= 7  THEN 'Potential Loyalists'
            WHEN (R.recency_score + R.frequency_score + R.monetary_score) >= 4  THEN 'At Risk'
            ELSE 'Lost Customers'
        END AS customer_segment
    FROM rfm_scores AS R
)
SELECT *
FROM customer_analytics
ORDER BY lifetime_value DESC;