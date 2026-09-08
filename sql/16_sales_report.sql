-- ============================================================
--   FULL DETAILED MONTHLY SALES TREND REPORT
--   Tables: orders, order_items, products, customers
--   Grain : One row per month (or per month + category)
-- ============================================================

WITH Monthly_base AS (
    SELECT
        TO_CHAR(O.Order_date, 'YYYY-MM') AS Order_month,
        COUNT(DISTINCT O.Customer_id) AS Unique_customers,
        COUNT(DISTINCT Oi.Order_id) AS Total_orders,
        SUM(Oi.Quantity) AS Units_sold,
        ROUND(SUM(Oi.List_price * Oi.Quantity), 2) AS Gross_revenue,
        ROUND(SUM(Oi.List_price * Oi.Quantity * Oi.Discount), 2)
            AS Total_discounts,
        ROUND(SUM(Oi.Total_value), 2) AS Net_revenue
    FROM Orders AS O
    INNER JOIN Order_items AS Oi
        ON
            O.Order_id = Oi.Order_id
    WHERE O.Order_status = 'Completed'
    GROUP BY 1
),

Monthly_kpi AS (
    SELECT
        Order_month,
        Unique_customers,
        Total_orders,
        Units_sold,
        Gross_revenue,
        Total_discounts,
        Net_revenue,
        ROUND(Net_revenue / NULLIF(Total_orders, 0), 2) AS Avg_order_value,
        ROUND(Total_discounts / NULLIF(Gross_revenue, 0) * 100, 2)
            AS Discount_rate_pct,
        ROUND(Net_revenue / NULLIF(Unique_customers, 0), 2)
            AS Revenue_per_customer,
        ROUND(Units_sold * 1.0 / NULLIF(Total_orders, 0), 2) AS Units_per_order,
        LAG(Net_revenue) OVER (ORDER BY Order_month) AS Prev_month_revenue,
        LAG(Total_orders) OVER (ORDER BY Order_month) AS Prev_month_orders,
        LAG(Unique_customers)
            OVER (ORDER BY Order_month)
            AS Prev_month_customers,
        ROUND(
            (Net_revenue - LAG(Net_revenue) OVER (ORDER BY Order_month))
            / NULLIF(LAG(Net_revenue) OVER (ORDER BY Order_month), 0) * 100, 2
        ) AS Revenue_growth_mom_pct,
        ROUND(
            (Total_orders - LAG(Total_orders) OVER (ORDER BY Order_month))
            / NULLIF(LAG(Total_orders) OVER (ORDER BY Order_month), 0) * 100, 2
        ) AS Orders_growth_mom_pct,
        ROUND(AVG(Net_revenue) OVER (
            ORDER BY Order_month
            ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
        ), 2) AS Rolling_3m_avg_revenue
    FROM Monthly_base
)

SELECT
    Order_month,
    Unique_customers,
    Total_orders,
    Units_sold,
    Gross_revenue,
    Total_discounts,
    Net_revenue,
    Avg_order_value,
    Discount_rate_pct,
    Revenue_per_customer,
    Units_per_order,
    Prev_month_revenue,
    Prev_month_orders,
    Prev_month_customers,
    Revenue_growth_mom_pct,
    Orders_growth_mom_pct,
    Rolling_3m_avg_revenue
FROM Monthly_kpi
