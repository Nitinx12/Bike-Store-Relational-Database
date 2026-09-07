WITH Sales_base AS (
    SELECT
        Oi.Product_id,
        O.Order_id,
        O.Customer_id,
        O.Store_id,
        O.Order_date,
        C.State,
        S.Store_name,
        Oi.Quantity,
        Oi.List_price,
        Oi.Discount,
        Oi.Quantity * Oi.List_price * (1 - Oi.Discount) AS Revenue,
        Oi.Quantity * Oi.List_price * Oi.Discount AS Discount_amount
    FROM Order_items AS Oi
    INNER JOIN Orders AS O
        ON
            Oi.Order_id = O.Order_id
    INNER JOIN Customers AS C
        ON
            O.Customer_id = C.Customer_id
    INNER JOIN Stores AS S ON
        O.Store_id = S.Store_id
),

Metrics AS (
    SELECT
        Product_id,
        SUM(Quantity) AS Total_units_sold,
        SUM(Revenue) AS Total_revenue,
        COUNT(DISTINCT Order_id) AS Total_orders,
        COUNT(DISTINCT Customer_id) AS Unique_customers,
        SUM(Discount_amount) AS Total_discount,
        MIN(Order_date) AS First_sale_date,
        MAX(Order_date) AS Last_sale_date
    FROM Sales_base
    GROUP BY
        Product_id
),

Inventory_metrics AS (
    SELECT
        Product_id,
        SUM(Quantity) AS Inventory_level
    FROM Stocks
    GROUP BY
        Product_id
),

Top_state AS (
    SELECT
        Product_id,
        State,
        ROW_NUMBER()
            OVER (
                PARTITION BY Product_id
                ORDER BY SUM(Revenue) DESC, State
            ) AS Rnk
    FROM Sales_base
    GROUP BY
        Product_id,
        State
),

Top_store AS (
    SELECT
        Product_id,
        Store_name,
        ROW_NUMBER()
            OVER (
                PARTITION BY Product_id
                ORDER BY SUM(Revenue) DESC, Store_name
            ) AS Rnk
    FROM Sales_base
    GROUP BY
        Product_id,
        Store_name
),

Dataset_date AS (
    SELECT MAX(Order_date) AS Last_dataset_date
    FROM Orders
),

Product_segmentation AS (
    SELECT
        Product_id,
        Total_revenue,
        Revenue_segment,
        AVG(Total_revenue)
            OVER (PARTITION BY Category_id)
            AS Avg_category_revenue,
        CASE
            WHEN
                Total_revenue
                > AVG(Total_revenue) OVER (PARTITION BY Category_id)
                THEN 'Above Average'
            ELSE 'Below Average'
        END AS Vs_category_avg
    FROM (
        SELECT
            P.Product_id,
            P.Category_id,
            SUM(Oi.Quantity * Oi.List_price * (1 - Oi.Discount))
                AS Total_revenue,
            CASE
                WHEN
                    SUM(Oi.Quantity * Oi.List_price * (1 - Oi.Discount))
                    >= 15000
                    THEN 'High Revenue'
                WHEN
                    SUM(
                        Oi.Quantity * Oi.List_price * (1 - Oi.Discount)
                    ) BETWEEN 3000 AND 14999
                    THEN 'Medium Revenue'
                ELSE 'Low Revenue'
            END AS Revenue_segment
        FROM Products AS P
        INNER JOIN Order_items AS Oi
            ON P.Product_id = Oi.Product_id
        GROUP BY
            P.Product_id,
            P.Category_id
    ) AS X
)

SELECT
    P.Product_name,
    B.Brand_name,
    C.Category_name,
    P.List_price,
    M.First_sale_date,
    M.Last_sale_date,
    Ts.State AS Top_state,
    Tss.Store_name AS Top_store,
    Pm.Vs_category_avg,
    DENSE_RANK()
        OVER (
            PARTITION BY P.Category_id
            ORDER BY COALESCE(M.Total_units_sold, 0) DESC
        ) AS Category_rank,
    COALESCE(M.Total_units_sold, 0) AS Total_units_sold,
    ROUND(COALESCE(M.Total_revenue, 0), 2) AS Total_revenue,
    COALESCE(M.Total_orders, 0) AS Total_orders,
    COALESCE(M.Unique_customers, 0) AS Unique_customers,
    CASE
        WHEN M.Total_units_sold > 0
            THEN ROUND(M.Total_revenue / M.Total_units_sold, 2)
    END AS Avg_selling_price,
    ROUND(COALESCE(M.Total_discount, 0), 2) AS Total_discount,
    Gd.Last_dataset_date - M.Last_sale_date AS Days_since_last_sale,
    COALESCE(Im.Inventory_level, 0) AS Inventory_level,
    COALESCE(Pm.Revenue_segment, 'Low Revenue') AS Revenue_segment,
    ROUND(Pm.Avg_category_revenue, 2) AS Avg_category_revenue,
    CASE
        WHEN M.Last_sale_date IS NULL
            THEN 'Never Sold'
        WHEN Gd.Last_dataset_date - M.Last_sale_date <= 365
            THEN 'Active'
        WHEN Gd.Last_dataset_date - M.Last_sale_date <= 1095
            THEN 'Slow Moving'
        ELSE 'Obsolete'
    END AS Lifecycle_status
FROM Products AS P
LEFT JOIN Brands AS B
    ON
        P.Brand_id = B.Brand_id
LEFT JOIN Categories AS C
    ON
        P.Category_id = C.Category_id
LEFT JOIN Metrics AS M
    ON
        P.Product_id = M.Product_id
LEFT JOIN Inventory_metrics AS Im
    ON
        P.Product_id = Im.Product_id
LEFT JOIN Top_state AS Ts
    ON
        P.Product_id = Ts.Product_id AND Ts.Rnk = 1
LEFT JOIN Top_store AS Tss
    ON
        P.Product_id = Tss.Product_id AND Tss.Rnk = 1
LEFT JOIN Product_segmentation AS Pm
    ON
        P.Product_id = Pm.Product_id
CROSS JOIN Dataset_date AS Gd;
