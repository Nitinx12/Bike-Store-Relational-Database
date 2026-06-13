-- ============================================================
--   FULL DETAILED MONTHLY SALES TREND REPORT
--   Tables: orders, order_items, products, customers
--   Grain : One row per month (or per month + category)
-- ============================================================

WITH Monthly_base AS(
    SELECT
        TO_CHAR(O.order_date,'YYYY-MM')                         AS order_month,
        COUNT(DISTINCT O.customer_id)                           AS unique_customers,
        COUNT(DISTINCT OI.order_id)                             AS total_orders,
        SUM(OI.quantity)                                        AS units_sold,
        ROUND(SUM(oi.list_price * oi.quantity), 2)              AS gross_revenue,
        ROUND(SUM(oi.discount), 2)                              AS total_discounts,
        ROUND(SUM(oi.total_value), 2)                           AS net_revenue
    FROM orders AS O
    INNER JOIN order_items AS OI ON
    OI.order_id = O.order_id
    WHERE O.order_status = 'Completed'
    GROUP BY order_month
),
Monthly_kpi AS(
    SELECT
        order_month,
        unique_customers,
        total_orders,
        units_sold,
        gross_revenue,
        total_discounts,
        net_revenue,
        ROUND(net_revenue / NULLIF(total_orders, 0), 2)             AS avg_order_value,
        ROUND(total_discounts / NULLIF(gross_revenue, 0) * 100, 2)  AS discount_rate_pct,
        ROUND(net_revenue / NULLIF(unique_customers, 0), 2)         AS revenue_per_customer,
        ROUND(units_sold * 1.0 / NULLIF(total_orders, 0), 2)        AS units_per_order,
        LAG(net_revenue)    OVER (ORDER BY order_month)                   AS prev_month_revenue,
        LAG(total_orders)   OVER (ORDER BY order_month)                   AS prev_month_orders,
        LAG(unique_customers) OVER (ORDER BY order_month)                 AS prev_month_customers,
        ROUND(
            (net_revenue - LAG(net_revenue) OVER (ORDER BY order_month))
            / NULLIF(LAG(net_revenue) OVER (ORDER BY order_month), 0) * 100, 2
        )                                                           AS revenue_growth_mom_pct,
        ROUND(
            (total_orders - LAG(total_orders) OVER (ORDER BY order_month))
            / NULLIF(LAG(total_orders) OVER (ORDER BY order_month), 0) * 100, 2
        )                                                           AS orders_growth_mom_pct,
        ROUND(AVG(net_revenue) OVER (
            ORDER BY order_month
            ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
        ), 2)                                                       AS rolling_3m_avg_revenue
    FROM Monthly_base
)
SELECT *
FROM Monthly_kpi