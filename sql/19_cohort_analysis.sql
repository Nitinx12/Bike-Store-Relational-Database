WITH Cohort_base AS (
    SELECT
        O.customer_id,
        DATE_TRUNC('MONTH', MIN(O.order_date)) AS cohort_month
    FROM orders AS O
    WHERE O.order_status = 'Completed'
    GROUP BY O.customer_id
),
Index_table AS (
    SELECT
        O.customer_id,
        CB.cohort_month,
        DATE_TRUNC('MONTH', O.order_date) AS activity_month,
        (
            EXTRACT(YEAR  FROM O.order_date)  * 12 +
            EXTRACT(MONTH FROM O.order_date)
        ) -
        (
            EXTRACT(YEAR  FROM CB.cohort_month) * 12 +  
            EXTRACT(MONTH FROM CB.cohort_month)
        ) AS index_number,
        OI.total_value
    FROM Cohort_base AS CB
    INNER JOIN orders AS O ON 
    O.customer_id = CB.customer_id
    INNER JOIN order_items AS OI ON 
    OI.order_id   = O.order_id
    WHERE O.order_status = 'Completed'                 
),
Cohort_summary AS (
    SELECT
        cohort_month,
        COUNT(DISTINCT customer_id) AS total_customers,
        SUM(total_value)            AS total_revenue
    FROM Index_table
    WHERE index_number = 0                             
    GROUP BY cohort_month
),
Cohort_retention AS (                                  
    SELECT
        IT.cohort_month,
        IT.index_number,
        CS.total_customers                                              AS cohort_size,
        COUNT(DISTINCT IT.customer_id)                                  AS active_customers,
        ROUND(100.0 * COUNT(DISTINCT IT.customer_id)
              / CS.total_customers, 1)                                  AS retention_rate,
        SUM(IT.total_value)                                             AS period_revenue
    FROM Index_table    AS IT
    INNER JOIN Cohort_summary AS CS ON 
    IT.cohort_month = CS.cohort_month
    GROUP BY 
        IT.cohort_month, 
        IT.index_number, 
        CS.total_customers
)
SELECT *
FROM Cohort_retention
ORDER BY cohort_month, index_number;