WITH cohort_base AS (
    SELECT
        o.customer_id,
        DATE_TRUNC('MONTH', MIN(o.order_date)) AS cohort_month
    FROM orders AS o
    WHERE
        o.order_status = 'Completed'
    GROUP BY
        o.customer_id
),

index_table AS (
    SELECT
        o.customer_id,
        cb.cohort_month,
        oi.total_value,
        DATE_TRUNC('MONTH', o.order_date) AS activity_month,
        (
            EXTRACT(YEAR FROM o.order_date) * 12
            + EXTRACT(MONTH FROM o.order_date)
        )
        - (
            EXTRACT(YEAR FROM cb.cohort_month) * 12
            + EXTRACT(MONTH FROM cb.cohort_month)
        ) AS index_number
    FROM cohort_base AS cb
    INNER JOIN orders AS o
        ON cb.customer_id = o.customer_id
    INNER JOIN order_items AS oi
        ON o.order_id = oi.order_id
    WHERE
        o.order_status = 'Completed'
),

cohort_summary AS (
    SELECT
        cohort_month,
        COUNT(DISTINCT customer_id) AS total_customers,
        SUM(total_value) AS total_revenue
    FROM
        index_table
    WHERE
        index_number = 0
    GROUP BY
        cohort_month
),

cohort_retention AS (
    SELECT
        it.cohort_month,
        it.index_number,
        cs.total_customers AS cohort_size,
        COUNT(DISTINCT it.customer_id) AS active_customers,
        ROUND(
            100.0 * COUNT(DISTINCT it.customer_id)
            / cs.total_customers, 1
        ) AS retention_rate,
        SUM(it.total_value) AS period_revenue
    FROM index_table AS it
    INNER JOIN cohort_summary AS cs
        ON it.cohort_month = cs.cohort_month
    GROUP BY
        it.cohort_month,
        it.index_number,
        cs.total_customers
)

SELECT
    cohort_month,
    index_number,
    cohort_size,
    active_customers,
    retention_rate,
    period_revenue
FROM
    cohort_retention
ORDER BY
    cohort_month,
    index_number;
