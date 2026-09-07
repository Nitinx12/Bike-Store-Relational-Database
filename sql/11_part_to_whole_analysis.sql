-- Which categories contribute the most to overall sales?

WITH Grand AS (
    SELECT SUM(Total_value) AS Grand_revenue
    FROM Order_items
),

Cate_revenue AS (
    SELECT
        C.Category_name,
        SUM(Oi.Total_value) AS Total_revenue
    FROM Categories AS C
    LEFT JOIN Products AS P
        ON
            C.Category_id = P.Category_id
    LEFT JOIN Order_items AS Oi
        ON
            P.Product_id = Oi.Product_id
    GROUP BY C.Category_name
)

SELECT
    Cr.Category_name,
    Cr.Total_revenue,
    ROUND(Cr.Total_revenue / G.Grand_revenue * 100, 2) AS Pct_of_total
FROM Cate_revenue AS Cr
CROSS JOIN Grand AS G
ORDER BY Pct_of_total DESC;
