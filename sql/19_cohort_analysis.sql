WITH Cohort_base AS (
    SELECT
        O.Customer_id,
        DATE_TRUNC('MONTH', MIN(O.Order_date)) AS Cohort_month
    FROM Orders AS O
    WHERE O.Order_status = 'Completed'
    GROUP BY O.Customer_id
),

Index_table AS (
    SELECT
        O.Customer_id,
        Cb.Cohort_month,
        Oi.Total_value,
        DATE_TRUNC('MONTH', O.Order_date) AS Activity_month,
        (
            EXTRACT(YEAR FROM O.Order_date) * 12
            + EXTRACT(MONTH FROM O.Order_date)
        )
        - (
            EXTRACT(YEAR FROM Cb.Cohort_month) * 12
            + EXTRACT(MONTH FROM Cb.Cohort_month)
        ) AS Index_number
    FROM Cohort_base AS Cb
    INNER JOIN Orders AS O
        ON
            Cb.Customer_id = O.Customer_id
    INNER JOIN Order_items AS Oi
        ON
            O.Order_id = Oi.Order_id
    WHERE O.Order_status = 'Completed'
),

Cohort_summary AS (
    SELECT
        Cohort_month,
        COUNT(DISTINCT Customer_id) AS Total_customers,
        SUM(Total_value) AS Total_revenue
    FROM Index_table
    WHERE Index_number = 0
    GROUP BY Cohort_month
),

Cohort_retention AS (
    SELECT
        It.Cohort_month,
        It.Index_number,
        Cs.Total_customers AS Cohort_size,
        COUNT(DISTINCT It.Customer_id) AS Active_customers,
        ROUND(
            100.0 * COUNT(DISTINCT It.Customer_id)
            / Cs.Total_customers, 1
        ) AS Retention_rate,
        SUM(It.Total_value) AS Period_revenue
    FROM Index_table AS It
    INNER JOIN Cohort_summary AS Cs
        ON
            It.Cohort_month = Cs.Cohort_month
    GROUP BY
        It.Cohort_month,
        It.Index_number,
        Cs.Total_customers
)

SELECT *
FROM Cohort_retention
ORDER BY Cohort_month, Index_number;
