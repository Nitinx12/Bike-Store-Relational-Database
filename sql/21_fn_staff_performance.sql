-- ============================================================
-- FUNCTION : fn_staff_performance
-- PURPOSE  : Measures each staff member's sales performance
--            including revenue, order handling, discount usage
--            and on-time shipping rate for a given period.
--
-- PARAMETERS:
--   p_start_date : Start of the analysis period
--                  Default = first day of current month
--   p_end_date   : End of the analysis period
--                  Default = today
--
-- RETURNS (one row per staff member):
--   staff_id             : Staff identifier
--   store_id             : Store the staff operates in
--   total_orders         : All orders handled in period
--   completed_orders     : Successfully completed orders
--   cancelled_orders     : Cancelled orders
--   cancellation_rate    : % of orders cancelled
--   total_revenue        : Revenue from completed orders
--   avg_order_value      : Average value per completed order
--   total_units_sold     : Total units sold
--   total_discount_given : Total discount amount applied
--   on_time_rate         : % of orders shipped by required date
--
-- HOW TO USE:
--
--   1. Default — current month
--      SELECT * FROM fn_staff_performance();
--
--   2. Custom date range
--      SELECT * FROM fn_staff_performance('2024-01-01', '2024-12-31');
--
--   3. Top 5 staff by revenue
--      SELECT staff_id, total_revenue, completed_orders
--      FROM fn_staff_performance('2024-01-01', '2024-12-31')
--      ORDER BY total_revenue DESC
--      LIMIT 5;
--
--   4. Staff with high cancellation rate
--      SELECT staff_id, cancellation_rate, cancelled_orders
--      FROM fn_staff_performance()
--      WHERE cancellation_rate > 20
--      ORDER BY cancellation_rate DESC;
--
--   5. Staff with poor on-time shipping
--      SELECT staff_id, on_time_rate, total_orders
--      FROM fn_staff_performance()
--      WHERE on_time_rate < 80
--      ORDER BY on_time_rate ASC;
--
--   6. Compare discount usage vs revenue per staff
--      SELECT staff_id, total_revenue,
--             total_discount_given,
--             ROUND(100.0 * total_discount_given
--                   / NULLIF(total_revenue, 0), 1) AS discount_pct
--      FROM fn_staff_performance('2024-01-01', '2024-12-31')
--      ORDER BY discount_pct DESC;
--
-- TABLES USED:
--   orders      → order_id, staff_id, store_id, order_date,
--                 order_status, required_date, shipped_date
--   order_items → order_id, product_id, quantity,
--                 total_value, discount
-- ============================================================

CREATE OR REPLACE FUNCTION fn_staff_performance(
    p_start_date  DATE DEFAULT (CURRENT_DATE - INTERVAL '3 years')::DATE,
    p_end_date    DATE DEFAULT CURRENT_DATE
)  
RETURNS TABLE(
    staff_id              BIGINT,
    store_id              BIGINT,
    total_orders          BIGINT,
    completed_orders      BIGINT,
    cancelled_orders      BIGINT,
    cancellation_rate     NUMERIC,
    total_revenue         NUMERIC,
    avg_order_value       NUMERIC,
    total_units_sold      NUMERIC,
    total_discount_given  NUMERIC,
    on_time_rate          NUMERIC
)
LANGUAGE plpgsql
AS $$
#variable_conflict use_column  
BEGIN
    RETURN QUERY
    WITH order_summary AS (
        SELECT
            O.staff_id,
            O.store_id,
            COUNT(O.order_id) AS total_orders,
            COUNT(
                CASE
                    WHEN O.order_status = 'Completed'
                    THEN O.order_id
                END
            ) AS completed_orders,
            COUNT(
                CASE
                    WHEN O.order_status = 'Cancelled'
                    THEN O.order_id
                END
            ) AS cancelled_orders
        FROM orders AS O
        WHERE O.order_date BETWEEN p_start_date AND p_end_date
        GROUP BY O.staff_id, O.store_id
    ),
    order_revenue AS (
        SELECT
            O.staff_id,
            O.order_id,
            SUM(OI.total_value) AS order_total,
            SUM(OI.quantity)    AS order_units,
            SUM(OI.discount)    AS order_discount
        FROM orders AS O
        INNER JOIN order_items AS OI ON OI.order_id = O.order_id
        WHERE O.order_status = 'Completed'
          AND O.order_date BETWEEN p_start_date AND p_end_date
        GROUP BY O.staff_id, O.order_id
    ),
    revenue_metrics AS (
        SELECT
            staff_id,
            SUM(order_total)::NUMERIC    AS total_revenue,
            AVG(order_total)::NUMERIC    AS avg_order_value,
            SUM(order_units)::NUMERIC    AS total_units_sold,
            SUM(order_discount)::NUMERIC AS total_discount_given
        FROM order_revenue
        GROUP BY staff_id
    ),
    fulfillment AS (
        SELECT
            O.staff_id,
            ROUND(
                100.0 * COUNT(CASE WHEN O.shipped_date <= O.required_date THEN 1 END)::NUMERIC
                / NULLIF(COUNT(CASE WHEN O.shipped_date IS NOT NULL THEN 1 END), 0),
            1)::NUMERIC AS on_time_rate
        FROM orders AS O
        WHERE O.order_status = 'Completed'
          AND O.order_date BETWEEN p_start_date AND p_end_date
        GROUP BY O.staff_id
    )
    SELECT
        OS.staff_id,
        OS.store_id,
        OS.total_orders,
        OS.completed_orders,
        OS.cancelled_orders,
        ROUND(
            100.0 * OS.cancelled_orders
            / NULLIF(OS.total_orders, 0),
        1)::NUMERIC                                   AS cancellation_rate,
        COALESCE(RM.total_revenue,        0::NUMERIC) AS total_revenue,
        COALESCE(RM.avg_order_value,      0::NUMERIC) AS avg_order_value,
        COALESCE(RM.total_units_sold,     0::NUMERIC) AS total_units_sold,
        COALESCE(RM.total_discount_given, 0::NUMERIC) AS total_discount_given,
        COALESCE(F.on_time_rate,          0::NUMERIC) AS on_time_rate
    FROM order_summary AS OS
    LEFT JOIN revenue_metrics AS RM ON 
    RM.staff_id = OS.staff_id
    LEFT JOIN fulfillment     AS F  ON 
    F.staff_id  = OS.staff_id
    ORDER BY total_revenue DESC;
END;
$$;