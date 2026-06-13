-- ============================================================
-- FUNCTION : fn_inventory_summary
-- PURPOSE  : Calculates a full inventory report per product
--            covering stock levels, sales movement,
--            reorder alerts and revenue impact
--            for a given date range.
--
-- PARAMETERS:
--   p_start_date        : Start of the analysis period
--                         Default = first day of current month
--   p_end_date          : End of the analysis period
--                         Default = today
--   p_reorder_threshold : Flag products at or below this stock qty
--                         Default = 10 units
--
-- RETURNS (one row per product):
--   product_id          : Unique product identifier
--   product_name        : Product name
--   model_year          : Product model year
--   current_stock       : Total units available across all stores
--   stock_out           : Units sold in the date range
--   reorder_alert       : TRUE if current stock <= threshold
--   potential_revenue   : list_price x current stock (stock value)
--   actual_revenue      : Revenue earned from completed orders
--   lost_revenue        : Revenue lost from cancelled orders
--
-- HOW TO USE:
--
--   1. Default — current month, threshold = 10
--      SELECT * FROM fn_inventory_summary();
--
--   2. Custom date range
--      SELECT * FROM fn_inventory_summary('2024-01-01', '2024-12-31');
--
--   3. Custom date range + custom threshold
--      SELECT * FROM fn_inventory_summary('2024-01-01', '2024-12-31', 25);
--
--   4. Reorder alerts only
--      SELECT product_name, current_stock, stock_out
--      FROM fn_inventory_summary()
--      WHERE reorder_alert = TRUE;
--
--   5. Revenue summary
--      SELECT
--          SUM(actual_revenue)    AS total_earned,
--          SUM(lost_revenue)      AS total_lost,
--          SUM(potential_revenue) AS total_stock_value
--      FROM fn_inventory_summary('2024-01-01', '2024-12-31');
--
-- TABLES USED:
--   products    → product_id, product_name, model_year, list_price
--   stocks      → product_id, quantity (aggregated across stores)
--   orders      → order_id, order_date, order_status
--   order_items → order_id, product_id, quantity, total_value
--
-- NOTES:
--   - stock_in is not tracked (no receipts/movement log in stocks table)
--   - Cancelled orders are used as a proxy for lost revenue
--   - Products with no stock show 0, not NULL
-- ============================================================

CREATE OR REPLACE FUNCTION fn_inventory_summary(
    p_start_date        DATE DEFAULT DATE_TRUNC('MONTH', CURRENT_DATE)::DATE,
    p_end_date          DATE DEFAULT CURRENT_DATE,
    p_reorder_threshold INT  DEFAULT 10
)
RETURNS TABLE (
    product_id        BIGINT,
    product_name      TEXT,
    model_year        BIGINT,
    current_stock     NUMERIC,    
    stock_out         NUMERIC, 
    reorder_alert     BOOLEAN,
    potential_revenue NUMERIC,
    actual_revenue    NUMERIC,
    lost_revenue      NUMERIC
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY

    WITH
    current_stock AS (
        SELECT
            S.product_id,
            SUM(S.quantity)::NUMERIC AS total_stock  
        FROM stocks AS S
        GROUP BY S.product_id
    ),
    stock_out AS (
        SELECT
            OI.product_id,
            SUM(OI.quantity)::NUMERIC AS units_sold
        FROM order_items AS OI
        INNER JOIN orders AS O ON 
        O.order_id = OI.order_id
        WHERE 
            O.order_status = 'Completed'
            AND O.order_date BETWEEN p_start_date AND p_end_date
        GROUP BY OI.product_id
    ),
    actual_revenue AS (
        SELECT
            OI.product_id,
            SUM(OI.total_value)::NUMERIC AS revenue
        FROM order_items AS OI
        INNER JOIN orders AS O ON 
        O.order_id = OI.order_id
        WHERE 
            O.order_status = 'Completed'
            AND O.order_date BETWEEN p_start_date AND p_end_date
        GROUP BY OI.product_id
    ),
    lost_revenue AS (
        SELECT
            OI.product_id,
            SUM(OI.total_value)::NUMERIC AS lost
        FROM order_items AS OI
        INNER JOIN orders AS O ON 
        O.order_id = OI.order_id
        WHERE 
            O.order_status = 'Cancelled'
            AND O.order_date   BETWEEN p_start_date AND p_end_date
        GROUP BY OI.product_id
    )

    SELECT
        P.product_id,
        P.product_name,
        P.model_year,
        COALESCE(CS.total_stock,  0::NUMERIC)                        AS current_stock,
        COALESCE(SO.units_sold,   0::NUMERIC)                        AS stock_out,
        COALESCE(CS.total_stock,  0::NUMERIC) <= p_reorder_threshold AS reorder_alert,
        P.list_price * COALESCE(CS.total_stock, 0::NUMERIC)          AS potential_revenue,
        COALESCE(AR.revenue,      0::NUMERIC)                        AS actual_revenue,
        COALESCE(LR.lost,         0::NUMERIC)                        AS lost_revenue
    FROM products            AS P
    LEFT JOIN current_stock  AS CS ON 
    CS.product_id = P.product_id
    LEFT JOIN stock_out      AS SO ON 
    SO.product_id = P.product_id
    LEFT JOIN actual_revenue AS AR ON 
    AR.product_id = P.product_id
    LEFT JOIN lost_revenue   AS LR ON 
    LR.product_id = P.product_id;
END;
$$;