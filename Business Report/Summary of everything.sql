WITH Revenue AS(
	SELECT
		SUM(OI.quantity * OI.list_price * (1 - OI.discount)) AS total_revenue,
		SUM(OI.quantity) AS total_units_sold,
		COUNT(DISTINCT O.order_id) AS total_orders
	FROM orders AS O
	INNER JOIN order_items AS OI ON
	O.order_id = OI.order_id
),
Customers AS(
	SELECT
		COUNT(DISTINCT customer_id) AS total_customers
	FROM orders
),
New_customers AS(
	SELECT COUNT(*) AS new_customers
	FROM(SELECT
			customer_id,
			MIN(order_date) AS first_order
		FROM orders
		GROUP BY
			customer_id) AS X
	
),
Stores AS(
	SELECT COUNT(*) AS total_stores
	FROM stores
),
Active_stores AS(
	SELECT COUNT(DISTINCT store_id) AS active_stores
	FROM orders
),
Staff AS(
	SELECT COUNT(*) AS total_staff
	FROM staffs
),
Inventory AS(
	SELECT SUM(quantity) AS total_inventory
	FROM stocks
)
SELECT
	ROUND(R.total_revenue,2) AS total_revenue,
	R.total_units_sold,
	R.total_orders,
	ROUND(R.total_revenue / R.total_orders,2) AS avg_order_value,
	C.total_customers,
	NC.new_customers,
	C.total_customers - NC.new_customers AS repeat_customers,
	S.total_stores,
	A.active_stores,
	ST.total_staff,
	I.total_inventory
FROM Revenue AS R
CROSS JOIN Customers C
CROSS JOIN New_customers NC
CROSS JOIN Stores S
CROSS JOIN Active_stores A
CROSS JOIN Staff ST
CROSS JOIN Inventory I