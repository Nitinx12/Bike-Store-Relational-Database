WITH sales AS (
    SELECT
        OI.product_id,
        SUM(OI.quantity) AS total_units_sold,
        MIN(O.order_date) AS first_sale_date,
        MAX(O.order_date) AS last_sale_date
    FROM order_items AS OI
    INNER JOIN orders AS O 
        ON O.order_id = OI.order_id
    GROUP BY
        OI.product_id
),
Inventory AS (
    SELECT
        product_id,
        SUM(quantity) AS current_stock
    FROM stocks
    GROUP BY
        product_id    
),
Dataset_date AS (
    SELECT MAX(order_date) AS last_dataset_date
    FROM orders
),
Velocity AS (
    SELECT
        S.product_id,
        S.total_units_sold,
        S.first_sale_date,
        S.last_sale_date,
        GREATEST(S.last_sale_date - S.first_sale_date, 1)::NUMERIC / 30.0 AS months_active
    FROM sales AS S
)
SELECT
    P.product_name,
    C.category_name,
    B.brand_name,
    COALESCE(I.current_stock, 0) AS current_stock,
    COALESCE(V.total_units_sold, 0) AS total_units_sold,
    ROUND((V.total_units_sold / V.months_active), 2) AS units_per_month,
    CASE
        WHEN COALESCE(I.current_stock, 0) = 0 THEN 0
        WHEN COALESCE(V.total_units_sold, 0) = 0 THEN 0
        ELSE ROUND((COALESCE(I.current_stock, 0)::NUMERIC / (V.total_units_sold / V.months_active)) * 30, 2)
    END AS days_of_inventory,
    V.last_sale_date,
    GD.last_dataset_date - V.last_sale_date AS days_since_last_sale,
    CASE
        WHEN COALESCE(I.current_stock, 0) = 0 
            THEN 'Out Of Stock'
        WHEN COALESCE(V.total_units_sold, 0) = 0 AND COALESCE(I.current_stock, 0) > 0 
            THEN 'Dead Stock'
        WHEN (V.total_units_sold / V.months_active) >= 20 AND I.current_stock < 20 
            THEN 'Stockout Risk'
        WHEN (V.total_units_sold / V.months_active) <= 2 AND I.current_stock > 50 
            THEN 'Overstock'
        WHEN (V.total_units_sold / V.months_active) >= 20 
            THEN 'Fast Moving'
        WHEN (V.total_units_sold / V.months_active) BETWEEN 5 AND 19 
            THEN 'Moderate'
        ELSE 'Slow Moving'
    END AS inventory_status
FROM products AS P
LEFT JOIN categories AS C 
    ON C.category_id = P.category_id
LEFT JOIN brands AS B 
    ON B.brand_id = P.brand_id
LEFT JOIN Inventory AS I 
    ON I.product_id = P.product_id
LEFT JOIN Velocity AS V 
    ON V.product_id = P.product_id
CROSS JOIN Dataset_date AS GD;