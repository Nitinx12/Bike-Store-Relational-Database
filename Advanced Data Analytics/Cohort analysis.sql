WITH Cohort_items AS(
	SELECT
		customer_id,
		DATE_TRUNC('MONTH',MIN(order_date)) :: DATE AS Cohort_months
	FROM orders
	GROUP BY
		customer_id
),
March_cohort AS(
	SELECT
		customer_id,
		Cohort_months
	FROM Cohort_items
	WHERE Cohort_months = '2017-03-01'
),
Index_table AS(
	SELECT
		O.customer_id,
		M.Cohort_months,
		DATE_TRUNC('MONTH',O.order_date :: DATE) :: DATE AS activity_month,
		(
		EXTRACT(YEAR FROM O.order_date) * 12 +
		EXTRACT(MONTH FROM O.order_date)
		)-
		(
		EXTRACT(YEAR FROM M.Cohort_months) * 12 +
		EXTRACT(MONTH FROM M.Cohort_months)
		) AS index_number,
		SUM(OI.total_value) AS revenue
	FROM March_cohort AS M
	INNER JOIN orders AS O ON
	M.customer_id = O.customer_id
	INNER JOIN order_items AS OI ON
	OI.order_id = O.order_id
	GROUP BY
		O.customer_id,
		M.Cohort_months,
		DATE_TRUNC('MONTH',O.order_date) :: DATE,
		index_number
),
Cohort_summary AS(
	SELECT
		Cohort_months,
		index_number,
		COUNT(DISTINCT customer_id) AS active_customers,
		SUM(revenue) AS total_revenue
	FROM Index_table
	WHERE index_number BETWEEN 0 AND 5
	GROUP BY
		Cohort_months,
		index_number
),
Calander_index AS(
	SELECT Generate_series(0,5) AS index_number
),
Base_cohort AS(
	SELECT
		COUNT(DISTINCT customer_id) AS base_size
	FROM March_cohort
)
SELECT
	'2017-03-01' :: DATE AS cohort_month,
	C.index_number,
	COALESCE(CS.active_customers,0) AS active_customers,
	B.base_size,
	COALESCE(CS.active_customers,0) * 100 / B.base_size AS retention_pct,
	COALESCE(CS.total_revenue,0) AS total_revenue
FROM Calander_index AS C
CROSS JOIN Base_cohort AS B
LEFT JOIN Cohort_summary AS CS ON
C.index_number = CS.index_number
ORDER BY
	C.index_number
