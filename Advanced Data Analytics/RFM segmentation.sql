WITH Customer_metrics AS(
    SELECT
        O.customer_id,
        MAX(O.order_date) AS last_purchase_date,
        COUNT(DISTINCT O.order_id) AS frequency,
        SUM(OI.quantity * OI.list_price * (1 - OI.discount)) AS monetary
    FROM orders O
   	INNER JOIN order_items OI
   	ON O.order_id = OI.order_id
    GROUP BY O.customer_id
),
Dataset_date AS(
    SELECT MAX(order_date) AS last_dataset_date
    FROM orders
),
RFM_base AS (
    SELECT
        C.customer_id,
        GD.last_dataset_date - C.last_purchase_date
        	AS recency_days,
        C.frequency,
        C.monetary
    FROM Customer_metrics C
    CROSS JOIN Dataset_date GD
),
RFM_scores AS (
    SELECT
        customer_id,
        recency_days,
        frequency,
        monetary,
        NTILE(5) OVER (ORDER BY recency_days DESC) AS r_score,
        NTILE(5) OVER (ORDER BY frequency) AS f_score,
        NTILE(5) OVER (ORDER BY monetary) AS m_score
    FROM RFM_base
)
SELECT
    customer_id,
    recency_days,
    frequency,
    ROUND(monetary, 2) AS monetary_value,
    r_score,
    f_score,
    m_score,
    CONCAT(r_score, f_score, m_score) AS rfm_code,
    CASE
        WHEN r_score >= 4 AND f_score >= 4 AND m_score >= 4
            THEN 'Champions'
        WHEN r_score >= 3 AND f_score >= 4
            THEN 'Loyal Customers'
        WHEN r_score >= 4 AND f_score <= 2
            THEN 'New Customers'
        WHEN r_score = 3 AND f_score = 3
            THEN 'Potential Loyalists'
        WHEN r_score <= 2 AND f_score >= 4
            THEN 'At Risk'
        WHEN r_score <= 2 AND f_score <= 2
            THEN 'Lost Customers'
       	ELSE 'Others'
    END AS customer_segment
FROM RFM_scores
ORDER BY monetary_value DESC;
