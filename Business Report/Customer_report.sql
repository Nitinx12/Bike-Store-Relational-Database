WITH Global_date AS(
	SELECT
		MAX(order_date) AS last_dataset_date
	FROM orders
),
Metrics AS(
	SELECT
		C.state,
		C.customer_id,
		CONCAT(C.first_name,' ',C.last_name) AS customer_full_name,
		SUM(OI.total_value) AS total_spent,
		SUM(OI.total_value) / COUNT(DISTINCT O.order_id) AS avg_value,
		COUNT(DISTINCT O.order_id) AS total_order,
		COUNT(DISTINCT CC.category_name) AS total_category,
		MIN(O.order_date) AS first_date,
		MAX(O.order_date) AS last_date
	FROM customers AS C
	INNER JOIN orders AS O ON
	C.customer_id = O.customer_id
	INNER JOIN order_items AS OI ON
	OI.order_id = O.order_id
	INNER JOIN products AS P ON
	P.product_id = OI.product_id
	INNER JOIN categories AS CC ON
	CC.category_id = P.category_id
	GROUP BY
		C.state,
		C.customer_id,
		CONCAT(C.first_name,' ',C.last_name)
),
Cate_spending AS(
	SELECT
		O.customer_id,
		C.category_name,
		SUM(OI.total_value) AS total_cate_spent,
		ROW_NUMBER()
			OVER(PARTITION BY O.customer_id
			ORDER BY SUM(OI.total_value) DESC) AS rnk
	FROM orders AS O
	INNER JOIN order_items AS OI ON
	O.order_id = OI.order_id
	INNER JOIN products AS P ON
	P.product_id = OI.product_id
	INNER JOIN categories AS C ON
	C.category_id = P.category_id
	GROUP BY
		O.customer_id,
		C.category_name
),
Primary_vs_secondary AS(
	SELECT
		C1.customer_id,
		C1.category_name AS primary_category,
		C1.total_cate_spent AS primary_category_spent,
		C2.category_name AS secondary_category,
		C2.total_cate_spent AS secondary_category_spent
	FROM Cate_spending AS C1
	LEFT JOIN Cate_spending AS C2 ON
	C2.customer_id = C1.customer_id AND C2.rnk = 2
	WHERE C1.rnk = 1
),
Days_between_orders AS(
	SELECT
		customer_id,
		AVG(order_date - previous_date) AS avg_days_between_orders
	FROM(SELECT
			O.customer_id,
			O.order_date,
			LAG(O.order_date)
				OVER(PARTITION BY O.customer_id
				ORDER BY O.order_date) AS previous_date
		FROM orders AS O) AS X
	WHERE X.previous_date IS NOT NULL
	GROUP BY
		customer_id
),
Weekend_weekday_spend AS(
	SELECT
		O.customer_id,
		SUM(CASE WHEN 
			EXTRACT(DOW FROM O.order_date) IN (0,6) THEN OI.total_value
			ELSE 0 END) AS weekend_spend,
		SUM(CASE
			WHEN EXTRACT(DOW FROM O.order_date) NOT IN(0,6) THEN OI.total_value
			ELSE 0 END) AS weekday_spend
	FROM orders AS O
	INNER JOIN order_items AS OI ON
	OI.order_id = O.order_id
	GROUP BY
		O.customer_id
),
Weekend_Weekday_Segment AS(
	SELECT
		customer_id,
		weekend_spend,
		weekday_spend,
		CASE
			WHEN weekend_spend > weekday_spend THEN 'Weekend Shopper'
			WHEN weekend_spend < weekday_spend THEN 'Weekday Shopper'
			ELSE 'Balanced'
		END AS shopping_pattern
	FROM Weekend_weekday_spend
)
SELECT
	M.state,
	M.customer_full_name,
	DENSE_RANK()
		OVER(PARTITION BY M.state
		ORDER BY M.total_spent DESC, M.total_order DESC) AS regional_rank,
	ROUND(M.total_spent,2) AS total_spent,
	ROUND(M.avg_value,2) AS avg_value,
	M.total_order,
	M.total_category,
	M.first_date,
	M.last_date,
	GD.last_dataset_date - M.last_date AS days_inactive,
	CASE
		WHEN M.total_order = 1 THEN 'One Time Buyer'
		WHEN M.total_order BETWEEN 2 AND 4 THEN 'Repeat Buyer'
		ELSE 'Loyal Customers'
	END AS customer_type,
	CASE
		WHEN GD.last_dataset_date - M.last_date <= 365 THEN 'Active'
		WHEN GD.last_dataset_date - M.last_date BETWEEN 366 AND 730 THEN 'Dormant'
		ELSE 'Churned'
	END AS customer_status,
	PS.primary_category,
	PS.primary_category_spent,
	PS.secondary_category,
	PS.secondary_category_spent,
	COALESCE(ROUND(DD.avg_days_between_orders,2),0) AS avg_days_between_orders,
	WWS.weekend_spend,
	WWS.weekday_spend,
	WWS.shopping_pattern
FROM Metrics AS M
LEFT JOIN Primary_vs_secondary AS PS ON
M.customer_id = PS.customer_id
LEFT JOIN Days_between_orders AS DD ON
M.customer_id = DD.customer_id
LEFT JOIN Weekend_Weekday_Segment AS WWS ON
M.customer_id = WWS.customer_id
CROSS JOIN Global_date AS GD;






















































