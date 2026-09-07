WITH Product_metric AS (
    SELECT
        B.Brand_id,
        B.Brand_name,
        COUNT(DISTINCT P.Product_id) AS Total_products,
        COUNT(DISTINCT Oi.Order_id) AS Total_orders,
        COUNT(DISTINCT O.Customer_id) AS Unique_customers,
        COALESCE(ROUND(SUM(Oi.Total_value), 2), 0) AS Total_revenue,
        COALESCE(ROUND(AVG(Oi.Total_value), 2), 0) AS Avg_order_value,
        COALESCE(SUM(Oi.Quantity), 0) AS Units_sold
    FROM Brands AS B
    LEFT JOIN Products AS P
        ON
            B.Brand_id = P.Brand_id
    LEFT JOIN Order_items AS Oi
        ON
            P.Product_id = Oi.Product_id
    LEFT JOIN Orders AS O
        ON
            Oi.Order_id = O.Order_id
    GROUP BY
        B.Brand_id,
        B.Brand_name
),

Grand_revenue AS (
    SELECT SUM(Total_revenue) AS Grand_revenue
    FROM Product_metric
)

SELECT
    Pm.Brand_id,
    Pm.Brand_name,
    Pm.Total_products,
    Pm.Units_sold,
    Pm.Unique_customers,
    Pm.Total_orders,
    Pm.Total_revenue,
    Pm.Avg_order_value,
    RANK()
        OVER (ORDER BY Pm.Total_revenue DESC) AS Brand_rank,
    ROUND(Pm.Total_revenue / NULLIF(Gr.Grand_revenue, 0) * 100, 2)
        AS Pct_of_total
FROM Product_metric AS Pm
CROSS JOIN Grand_revenue AS Gr
ORDER BY Brand_rank ASC;
