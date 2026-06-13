-- =====================================================================
-- FUNCTION : fn_store_performance
-- PURPOSE  : Returns a comprehensive performance summary for each store
--            covering orders, revenue, fulfillment, staff, customers,
--            and inventory metrics within a given date range.
--
-- RETURNS  : One row per store regardless of activity (LEFT JOIN base)
--            Stores with no orders still appear with zero metrics.
--
-- PARAMETERS:
--   p_start_date  DATE  Start of the reporting period (inclusive)
--                       Default: '2016-01-01'
--   p_end_date    DATE  End of the reporting period   (inclusive)
--                       Default: '2018-12-28'
--
-- USAGE:
--   -- 1. Full dataset (uses defaults)
--   SELECT * FROM fn_store_performance();
--
--   -- 2. Custom date range
--   SELECT * FROM fn_store_performance('2017-01-01', '2017-12-31');
--
--   -- 3. Single month
--   SELECT * FROM fn_store_performance('2018-06-01', '2018-06-30');
--
--   -- 4. Filter by specific store
--   SELECT * FROM fn_store_performance()
--   WHERE store_name = 'Santa Cruz Bikes';
--
--   -- 5. Only top performing stores by revenue
--   SELECT * FROM fn_store_performance()
--   WHERE total_revenue > 50000
--   ORDER BY total_revenue DESC;
--
-- DEPENDENCIES:
--   Tables  : stores, orders, order_items, staffs, stocks
--   Columns : orders.customer_id, stocks.quantity (assumed standard)
--
-- NOTES:
--   - stock metrics are NOT date-filtered (reflects current inventory)
--   - staff count reflects all staff assigned, not active in date range
--   - on_time_rate only counts orders where shipped_date IS NOT NULL
--   - repeat_customers = customers with more than 1 order in date range
-- =====================================================================

CREATE OR REPLACE FUNCTION fn_store_performance(
    p_start_date  DATE DEFAULT '2016-01-01',
    p_end_date    DATE DEFAULT '2018-12-28'
)
RETURNS TABLE(
    store_id              BIGINT,
    store_name            TEXT,
    city                  TEXT,
    state                 TEXT,
    total_orders          BIGINT,
    completed_orders      BIGINT,
    cancelled_orders      BIGINT,
    cancellation_rate     NUMERIC,
    total_revenue         NUMERIC,
    avg_order_value       NUMERIC,
    total_units_sold      NUMERIC,
    total_discount_given  NUMERIC,
    on_time_rate          NUMERIC,
    total_staff           BIGINT,
    avg_revenue_per_staff NUMERIC,
    total_customers       BIGINT,
    repeat_customers      BIGINT,
    total_stock_quantity  NUMERIC
)
LANGUAGE plpgsql
AS $$
#variable_conflict use_column
BEGIN

    RETURN QUERY

    WITH order_summary AS (
        SELECT
            O.store_id,
            COUNT(O.order_id)                                                    AS total_orders,
            COUNT(CASE WHEN O.order_status = 'Completed' THEN O.order_id END)    AS completed_orders,
            COUNT(CASE WHEN O.order_status = 'Cancelled' THEN O.order_id END)    AS cancelled_orders
        FROM orders AS O
        WHERE O.order_date BETWEEN p_start_date AND p_end_date
        GROUP BY O.store_id
    ),
    order_revenue AS (
        SELECT
            O.store_id,
            O.order_id,
            SUM(OI.total_value) AS order_total,
            SUM(OI.quantity)    AS order_units,
            SUM(OI.discount)    AS order_discount
        FROM orders AS O
        INNER JOIN order_items AS OI ON OI.order_id = O.order_id
        WHERE O.order_status = 'Completed'
          AND O.order_date BETWEEN p_start_date AND p_end_date
        GROUP BY O.store_id, O.order_id
    ),
    revenue_metrics AS (
        SELECT
            OR2.store_id,
            SUM(OR2.order_total)::NUMERIC    AS total_revenue,
            AVG(OR2.order_total)::NUMERIC    AS avg_order_value,
            SUM(OR2.order_units)::NUMERIC    AS total_units_sold,
            SUM(OR2.order_discount)::NUMERIC AS total_discount_given
        FROM order_revenue AS OR2
        GROUP BY OR2.store_id
    ),
    fulfillment AS (
        SELECT
            O.store_id,
            ROUND(
                100.0 * COUNT(CASE WHEN O.shipped_date <= O.required_date THEN 1 END)::NUMERIC
                / NULLIF(COUNT(CASE WHEN O.shipped_date IS NOT NULL THEN 1 END), 0),
            1)::NUMERIC AS on_time_rate
        FROM orders AS O
        WHERE O.order_status = 'Completed'
          AND O.order_date BETWEEN p_start_date AND p_end_date
        GROUP BY O.store_id
    ),
    staff_metrics AS (
        SELECT
            S.store_id,
            COUNT(S.staff_id) AS total_staff
        FROM staffs AS S
        GROUP BY S.store_id
    ),
    customer_metrics AS (
        SELECT
            O.store_id,
            COUNT(DISTINCT O.customer_id)                                        AS total_customers,
            COUNT(DISTINCT CASE
                WHEN order_counts.order_count > 1 THEN O.customer_id
            END)                                                                 AS repeat_customers
        FROM orders AS O
        INNER JOIN (
            SELECT 
                customer_id, 
                COUNT(order_id) AS order_count
            FROM orders
            WHERE order_date BETWEEN p_start_date AND p_end_date
            GROUP BY customer_id
        ) AS order_counts ON order_counts.customer_id = O.customer_id
        WHERE O.order_date BETWEEN p_start_date AND p_end_date
        GROUP BY O.store_id
    ),
    stock_metrics AS (
        SELECT
            SK.store_id,
            SUM(SK.quantity)::NUMERIC AS total_stock_quantity
        FROM stocks AS SK
        GROUP BY SK.store_id
    )
    SELECT
        ST.store_id,
        ST.store_name,
        ST.city,
        ST.state,
        COALESCE(OS.total_orders,             0)          AS total_orders,
        COALESCE(OS.completed_orders,         0)          AS completed_orders,
        COALESCE(OS.cancelled_orders,         0)          AS cancelled_orders,
        ROUND(
            100.0 * COALESCE(OS.cancelled_orders, 0)
            / NULLIF(COALESCE(OS.total_orders, 0), 0),
        1)::NUMERIC                                       AS cancellation_rate,
        COALESCE(RM.total_revenue,        0::NUMERIC)     AS total_revenue,
        COALESCE(RM.avg_order_value,      0::NUMERIC)     AS avg_order_value,
        COALESCE(RM.total_units_sold,     0::NUMERIC)     AS total_units_sold,
        COALESCE(RM.total_discount_given, 0::NUMERIC)     AS total_discount_given,
        COALESCE(F.on_time_rate,          0::NUMERIC)     AS on_time_rate,
        COALESCE(SM.total_staff,          0)              AS total_staff,
        ROUND(
            COALESCE(RM.total_revenue, 0)
            / NULLIF(SM.total_staff, 0),
        2)::NUMERIC                                       AS avg_revenue_per_staff,
        COALESCE(CM.total_customers,      0)              AS total_customers,
        COALESCE(CM.repeat_customers,     0)              AS repeat_customers,
        COALESCE(SK.total_stock_quantity, 0::NUMERIC)     AS total_stock_quantity
    FROM stores AS ST
    LEFT JOIN order_summary    AS OS ON OS.store_id = ST.store_id
    LEFT JOIN revenue_metrics  AS RM ON RM.store_id = ST.store_id
    LEFT JOIN fulfillment      AS F  ON F.store_id  = ST.store_id
    LEFT JOIN staff_metrics    AS SM ON SM.store_id = ST.store_id
    LEFT JOIN customer_metrics AS CM ON CM.store_id = ST.store_id
    LEFT JOIN stock_metrics    AS SK ON SK.store_id = ST.store_id
    ORDER BY total_revenue DESC;

END;
$$;