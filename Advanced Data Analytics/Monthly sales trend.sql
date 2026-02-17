WITH Monthly_sales AS(
	SELECT
		TO_CHAR(O.order_date,'YYYY-MM') AS sales_month,
		SUM(OI.quantity) AS total_units_sold,
		SUM(OI.quantity * OI.list_price * (1 - OI.discount)) AS total_revenue,
		COUNT(DISTINCT O.order_id) AS total_orders
	FROM orders AS O
	INNER JOIN order_items AS OI ON
	O.order_id = OI.order_id
	GROUP BY
		TO_CHAR(O.order_date,'YYYY-MM')
),
Growth AS(
	SELECT
		sales_month,
		total_units_sold,
		total_revenue,
		total_orders,
		LAG(total_revenue)
			OVER(ORDER BY sales_month) AS prev_month_revenue
	FROM Monthly_sales
)
SELECT
	sales_month,
	COALESCE(total_units_sold,0) AS total_units_sold,
	COALESCE(total_orders,0) AS total_orders,
	ROUND(COALESCE(total_revenue,0),2) AS total_revenue,
	CASE
		WHEN prev_month_revenue IS NULL
		THEN 0
		ELSE ROUND((total_revenue - prev_month_revenue) / prev_month_revenue * 100,2)
	END AS mom_growth_percent
FROM Growth
ORDER BY
	sales_month