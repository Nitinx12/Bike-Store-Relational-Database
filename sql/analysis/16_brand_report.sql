-- 16_brand_report.sql: brand-level sales performance, ranked by revenue.
-- Every brand appears even with no products/sales (LEFT JOIN chain).
-- Source for reports/brands_performance.md. Run with psql -f sql/analysis/16_brand_report.sql
WITH brand_stats AS (
    SELECT
        b.brand_name AS brand,
        COUNT(DISTINCT p.product_id) AS total_products,
        COALESCE(SUM(i.quantity), 0) AS units_sold,
        COUNT(DISTINCT o.customer_id) AS unique_customers,
        COUNT(DISTINCT o.order_id) AS total_orders,
        COALESCE(SUM(i.total_value), 0) AS total_revenue,
        COALESCE(AVG(i.total_value), 0) AS avg_order_value
    FROM
        public.brands AS b
        LEFT JOIN public.products AS p ON p.brand_id = b.brand_id
        LEFT JOIN public.order_items AS i ON i.product_id = p.product_id
        LEFT JOIN public.orders AS o ON o.order_id = i.order_id
    GROUP BY
        b.brand_name
),
grand_revenue AS (
    SELECT SUM(total_revenue) AS grand_total FROM brand_stats
)
SELECT
    RANK() OVER (ORDER BY s.total_revenue DESC) AS rank,
    s.brand,
    s.total_products AS products,
    s.units_sold AS units_sold,
    s.unique_customers,
    s.total_orders AS orders,
    ROUND(s.total_revenue, 2) AS total_revenue,
    ROUND(s.avg_order_value, 2) AS avg_order_value,
    ROUND(s.total_revenue / NULLIF(g.grand_total, 0) * 100, 2) AS pct_of_total
FROM
    brand_stats AS s
    CROSS JOIN grand_revenue AS g
ORDER BY
    s.total_revenue DESC;
