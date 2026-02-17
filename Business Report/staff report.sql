WITH Sales_base AS(
	SELECT
		O.staff_id,
		O.order_id,
		O.customer_id,
		O.store_id,
		O.order_date,
		OI.quantity,
		OI.quantity * OI.list_price * (1 - OI.discount) AS revenue
	FROM orders AS O
	INNER JOIN order_items AS OI ON
	OI.order_id = O.order_id
),
Metrics AS(
	SELECT
		Staff_id,
		COUNT(DISTINCT order_id) AS total_orders,
		SUM(quantity) AS total_units_sold,
		SUM(revenue) AS total_revenue,
		COUNT(DISTINCT customer_id) AS unique_customers,
		MIN(order_date) AS first_sale_date,
		MAX(order_date) AS last_sale_date
	FROM sales_base
	GROUP BY
		staff_id
),
Dataset_date AS(
	SELECT MAX(order_date) AS last_dataset_date
	FROM orders
)
SELECT
	S.staff_id,
	CONCAT(S.first_name,' ',S.last_name) AS staff_name,
	ST.store_name,
	COALESCE(M.total_orders,0) AS total_orders,
	COALESCE(M.total_units_sold,0) AS total_units_sold,
	ROUND(COALESCE(M.total_revenue),0) AS total_revenue,
	COALESCE(M.unique_customers,0) AS unique_customers,
	CASE
		WHEN M.total_orders > 0
		THEN ROUND(M.total_revenue / M.total_orders,2)
		ELSE NULL
	END AS avg_order_value,
	M.first_sale_date,
	M.last_sale_date,
	GD.last_dataset_date - M.last_sale_date AS days_since_last_sale,
	CASE
		WHEN M.total_orders > 0
		THEN ROUND(M.total_orders / 
			GREATEST(
					(M.last_sale_date - M.first_sale_date) / 30,1),2)
		ELSE 0
	END AS orders_per_month,
	DENSE_RANK()
		OVER(PARTITION BY S.store_id
		ORDER BY COALESCE(M.total_revenue,0) DESC) AS store_rank,
	DENSE_RANK()
		OVER(ORDER BY COALESCE(M.total_revenue,0) DESC) AS company_rank,
	CASE
		WHEN M.last_sale_date IS NULL
		THEN 'No Sales'
		WHEN GD.last_dataset_date - M.last_sale_date <= 90
		THEN 'Active'
		ELSE 'Inactive'
	END AS staff_status
FROM staffs AS S
LEFT JOIN Metrics AS M ON
M.staff_id = S.staff_id
LEFT JOIN stores AS ST ON
ST.store_id = S.store_id
CROSS JOIN Dataset_date AS GD;
