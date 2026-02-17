WITH Sales_base AS(
	SELECT
		OI.product_id,
		O.order_id,
		O.customer_id,
		O.store_id,
		O.order_date,
		C.state,
		S.store_name,
		OI.quantity,
		OI.list_price,
		OI.discount,
		OI.quantity * OI.list_price * (1 - OI.discount) AS revenue,
		OI.quantity * OI.list_price * OI.discount AS discount_amount
	FROM order_items AS OI
	INNER JOIN orders AS O ON
	OI.order_id = O.order_id
	INNER JOIN customers AS C ON
	C.customer_id = O.customer_id
	INNER JOIN stores AS S ON
	S.store_id = O.store_id
),
Metrics AS(
	SELECT
		product_id,
		SUM(quantity) AS total_units_sold,
		SUM(revenue) AS total_revenue,
		COUNT(DISTINCT order_id) AS total_orders,
		COUNT(DISTINCT customer_id) AS unique_customers,
		SUM(discount_amount) AS total_discount,
		MIN(order_date) AS first_sale_date,
		MAX(order_date) AS last_sale_date
	FROM Sales_base
	GROUP BY
		product_id
),
Inventory_metrics AS(
	SELECT
		product_id,
		SUM(quantity) AS inventory_level
	FROM stocks
	GROUP BY
		product_id
),
Top_state AS(
	SELECT
		product_id,
		state,
		ROW_NUMBER()
			OVER(PARTITION BY product_id
			ORDER BY SUM(revenue) DESC) AS rnk
	FROM Sales_base
	GROUP BY
		product_id,
		state
),
Top_store AS(
	SELECT
		product_id,
		store_name,
		ROW_NUMBER()
			OVER(PARTITION BY product_id
			ORDER BY SUM(revenue) DESC) AS rnk
	FROM Sales_base
	GROUP BY
		product_id,
		store_name
),
dataset_date AS(
	SELECT 
		MAX(order_date) AS last_dataset_date
	FROM orders
),
product_segmentation AS(
	SELECT
		product_id,
		total_revenue,
		revenue_segment,
		AVG(total_revenue) OVER(PARTITION BY category_id) AS avg_category_revenue,
		CASE
			WHEN total_revenue > AVG(total_revenue) OVER(PARTITION BY category_id)
			THEN 'Above average'
			ELSE 'Below average'
		END AS performance_stats
	FROM(SELECT
			P.product_id,
			P.category_id,
			SUM(OI.total_value) AS total_revenue,
			CASE
				WHEN SUM(OI.total_value) >= 15000 THEN 'High Revenue'
				WHEN SUM(OI.total_value) BETWEEN 3000 AND 14999 THEN 'Medium Revenue'
				ELSE 'Low Revenue'
			END AS revenue_segment
		FROM products AS P
		INNER JOIN order_items AS OI ON
		P.product_id = OI.product_id
		GROUP BY
			P.product_id,
			P.category_id) AS X
)
SELECT
	P.product_name,
	B.brand_name,
	C.category_name,
	P.list_price,
	DENSE_RANK()
		OVER(PARTITION BY P.category_id
		ORDER BY COALESCE(M.total_units_sold,0) DESC) AS category_rank,
	ROUND(COALESCE(M.total_units_sold,0),2) AS total_units_sold,
	ROUND(COALESCE(M.total_revenue,0),2) AS total_revenue,
	COALESCE(M.total_orders,0) AS total_orders,
	COALESCE(M.unique_customers,0) AS unique_customers,
	CASE
		WHEN M.total_units_sold > 0
		THEN ROUND(M.total_revenue / M.total_units_sold,2)
		ELSE NULL
	END AS avg_selling_price,
	ROUND(COALESCE(M.total_discount,0),2) AS total_discount,
	M.first_sale_date,
	M.last_sale_date,
	GD.last_dataset_date - M.last_sale_date AS days_since_last_sale,
	TS.state AS top_state,
	TSS.store_name AS top_store,
	COALESCE(IM.inventory_level,0) AS inventory_level,
	PM.revenue_segment,
	ROUND(PM.avg_category_revenue,2) AS avg_category_revenue,
	PM.performance_stats,
	CASE
		WHEN M.last_sale_date IS NULL
		THEN 'Never_sold'
		WHEN GD.last_dataset_date - M.last_sale_date <= 365
		THEN 'Active'
		WHEN GD.last_dataset_date - M.last_sale_date <= 1095
		THEN 'Slow Moving'
		ELSE 'Obsolete'
	END AS lifecycle_status
FROM products AS P
LEFT JOIN brands AS B ON
B.brand_id = P.brand_id
LEFT JOIN categories AS C ON
C.category_id = P.category_id
LEFT JOIN Metrics AS M ON
M.product_id = P.product_id
LEFT JOIN Inventory_metrics AS IM ON
P.product_id = IM.product_id
LEFT JOIN Top_state AS TS ON
TS.product_id = P.product_id AND TS.rnk = 1
LEFT JOIN Top_store AS TSS ON
TSS.product_id = P.product_id AND TSS.rnk = 1
LEFT JOIN product_segmentation AS PM ON
PM.product_id = P.product_id
CROSS JOIN dataset_date AS GD;