WITH monthly_base AS (
    SELECT
        TO_CHAR(o.order_date, 'YYYY-MM') AS order_month,
        COUNT(DISTINCT o.customer_id) AS unique_customers,
        COUNT(DISTINCT oi.order_id) AS total_orders,
        SUM(oi.quantity) AS units_sold,
        ROUND(SUM(oi.list_price * oi.quantity), 2) AS gross_revenue,
        ROUND(SUM(oi.list_price * oi.quantity * oi.discount), 2)
            AS total_discounts,
        ROUND(SUM(oi.total_value), 2) AS net_revenue
    FROM orders AS o
    INNER JOIN order_items AS oi
        ON o.order_id = oi.order_id
    WHERE
        o.order_status = 'Completed'
    GROUP BY
        TO_CHAR(o.order_date, 'YYYY-MM')
),

monthly_kpi AS (
    SELECT
        order_month,
        unique_customers,
        total_orders,
        units_sold,
        gross_revenue,
        total_discounts,
        net_revenue,
        ROUND(net_revenue / NULLIF(total_orders, 0), 2) AS avg_order_value,
        ROUND(total_discounts / NULLIF(gross_revenue, 0) * 100, 2)
            AS discount_rate_pct,
        ROUND(net_revenue / NULLIF(unique_customers, 0), 2)
            AS revenue_per_customer,
        ROUND(units_sold * 1.0 / NULLIF(total_orders, 0), 2) AS units_per_order,
        LAG(net_revenue) OVER (ORDER BY order_month) AS prev_month_revenue,
        LAG(total_orders) OVER (ORDER BY order_month) AS prev_month_orders,
        LAG(unique_customers)
            OVER (ORDER BY order_month)
            AS prev_month_customers,
        ROUND(
            (net_revenue - LAG(net_revenue) OVER (ORDER BY order_month))
            / NULLIF(LAG(net_revenue) OVER (ORDER BY order_month), 0) * 100, 2
        ) AS revenue_growth_mom_pct,
        ROUND(
            (total_orders - LAG(total_orders) OVER (ORDER BY order_month))
            / NULLIF(LAG(total_orders) OVER (ORDER BY order_month), 0) * 100, 2
        ) AS orders_growth_mom_pct,
        ROUND(AVG(net_revenue) OVER (
            ORDER BY order_month
            ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
        ), 2) AS rolling_3m_avg_revenue
    FROM
        monthly_base
)

SELECT
    order_month,
    unique_customers,
    total_orders,
    units_sold,
    gross_revenue,
    total_discounts,
    net_revenue,
    avg_order_value,
    discount_rate_pct,
    revenue_per_customer,
    units_per_order,
    prev_month_revenue,
    prev_month_orders,
    prev_month_customers,
    revenue_growth_mom_pct,
    orders_growth_mom_pct,
    rolling_3m_avg_revenue
FROM
    monthly_kpi
ORDER BY
    order_month;
