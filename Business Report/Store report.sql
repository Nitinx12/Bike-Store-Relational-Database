WITH Sales_base AS(
	SELECT
		O.store_id,
		O.order_id,
		O.customer_id,
		O.staff_id,
		O.order_date,
		OI.quantity,
		OI.quantity * OI.list_price * (1 - OI.discount) AS revenue
	FROM orders AS O
	INNER JOIN order_items AS OI ON
	OI.order_id = O.order_id
),
Metrics AS(
	SELECT
		store_id,
		COUNT(DISTINCT order_id) AS total_orders,
		SUM(quantity) AS total_units_sold,
		SUM(revenue) AS total_revenue,
		COUNT(DISTINCT customer_id) AS unique_customers,
		MIN(order_date) AS first_sale_date,
		MAX(order_date) AS last_sale_date
	FROM Sales_base
	GROUP BY
		store_id		
),
First_purchase AS(
	SELECT
		customer_id,
		MIN(order_date) AS first_order_date
	FROM orders
	GROUP BY
		customer_id
),
New_customers AS(
	SELECT
		O.store_id,
		COUNT(DISTINCT O.customer_id) AS new_customers
	FROM orders AS O
	INNER JOIN First_purchase AS F ON
	F.customer_id = O.customer_id
	AND O.order_date = F.first_order_date
	GROUP BY
		store_id		
),
Staff_count AS(
	SELECT
		store_id,
		COUNT(*) AS staff_count
	FROM staffs
	GROUP BY
		store_id
),
Inventory AS(
	SELECT
		store_id,
		SUM(quantity) AS inventory_level
	FROM stocks
	GROUP BY
		store_id
),
Dataset_date AS(
	SELECT MAX(order_date) AS last_dataset_date
	FROM orders
)
SELECT
	ST.store_id,
	ST.store_name,
	ST.city,
	ST.state,
	COALESCE(M.total_orders,0) AS total_orders,
	COALESCE(M.total_units_sold, 0) AS total_units_sold,
    ROUND(COALESCE(M.total_revenue, 0), 2) AS total_revenue,
    COALESCE(M.unique_customers, 0) AS unique_customers,
	CASE
		WHEN M.total_orders > 0
		THEN ROUND(M.total_revenue / M.total_orders, 2)
		ELSE NULL
	END AS avg_order_value,
	COALESCE(NC.new_customers, 0) AS new_customers,
	COALESCE(M.unique_customers, 0) - COALESCE(NC.new_customers, 0) AS repeat_customers,
	COALESCE(SC.staff_count, 0) AS staff_count,
	CASE
		WHEN SC.staff_count > 0
		THEN ROUND(M.total_revenue / SC.staff_count, 2)
		ELSE NULL
	END AS revenue_per_staff,
	COALESCE(I.inventory_level, 0) AS inventory_level,
	M.first_sale_date,
    M.last_sale_date,
    GD.last_dataset_date - M.last_sale_date AS days_since_last_sale,
	DENSE_RANK() OVER(
        ORDER BY COALESCE(M.total_revenue, 0) DESC) AS store_rank,
	CASE
        WHEN M.last_sale_date IS NULL
        THEN 'No Sales'
        WHEN GD.last_dataset_date - M.last_sale_date <= 90
        THEN 'Active'
        ELSE 'Inactive'
    END AS store_status
FROM stores AS ST
LEFT JOIN Metrics AS M
ON M.store_id = ST.store_id
LEFT JOIN New_customers NC
ON NC.store_id = ST.store_id
LEFT JOIN Staff_count SC
ON SC.store_id = ST.store_id
LEFT JOIN Inventory I
ON I.store_id = ST.store_id
CROSS JOIN Dataset_date GD;
	
















































































































