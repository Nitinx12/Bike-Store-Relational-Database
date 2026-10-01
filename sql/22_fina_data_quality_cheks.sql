WITH checks AS (

    -- 1. Completed orders with no shipped_date (population: completed orders)
    SELECT 1 AS sort_order,
           '01_completed_orders_missing_shipped_date' AS check_name,
           COUNT(*) FILTER (WHERE shipped_date IS NULL) AS failed_rows,
           COUNT(*) AS total_rows
    FROM orders
    WHERE order_status = 'Completed'

    UNION ALL

    -- 2. Non-completed orders that already have a shipped_date (population: non-completed orders)
    SELECT 2,
           '02_non_completed_orders_with_shipped_date',
           COUNT(*) FILTER (WHERE shipped_date IS NOT NULL),
           COUNT(*)
    FROM orders
    WHERE order_status <> 'Completed'

    UNION ALL

    -- 3. Shipped/required date earlier than order date (population: all orders)
    SELECT 3,
           '03_dates_before_order_date',
           COUNT(*) FILTER (WHERE shipped_date < order_date
                               OR required_date < order_date),
           COUNT(*)
    FROM orders

    UNION ALL

    -- 4. Line total_value <> quantity * list_price * (1 - discount), with rounding tolerance
    SELECT 4,
           '04_invalid_order_line_total_value',
           COUNT(*) FILTER (
               WHERE total_value IS NULL
                  OR ABS(total_value - quantity * list_price * (1 - discount)) > 0.01
           ),
           COUNT(*)
    FROM order_items

    UNION ALL

    -- 5. Line price <> catalogue price (population: all order lines)
    SELECT 5,
           '05_order_line_price_mismatch',
           COUNT(*) FILTER (WHERE P.product_id IS NOT NULL
                              AND OI.list_price <> P.list_price),
           COUNT(*)
    FROM order_items AS OI
    LEFT JOIN products AS P
           ON P.product_id = OI.product_id

    UNION ALL

    -- 6. Orders with orphan customer_id (population: all orders)
    SELECT 6,
           '06_orphan_customer_id',
           COUNT(*) FILTER (WHERE C.customer_id IS NULL),
           COUNT(*)
    FROM orders AS O
    LEFT JOIN customers AS C
           ON C.customer_id = O.customer_id

    UNION ALL

    -- 7. Orders handled by staff from another store (population: all orders)
    SELECT 7,
           '07_staff_store_mismatch',
           COUNT(*) FILTER (WHERE S.staff_id IS NOT NULL
                              AND S.store_id <> O.store_id),
           COUNT(*)
    FROM orders AS O
    LEFT JOIN staffs AS S
           ON S.staff_id = O.staff_id

    UNION ALL

    -- 8. Products with no stock record (population: all products)
    SELECT 8,
           '08_products_without_stock_record',
           COUNT(*) FILTER (WHERE NOT EXISTS (
               SELECT 1 FROM stocks ST WHERE ST.product_id = P.product_id)),
           COUNT(*)
    FROM products AS P

    UNION ALL

    -- 9. Products never sold (population: all products)
    SELECT 9,
           '09_products_never_sold',
           COUNT(*) FILTER (WHERE NOT EXISTS (
               SELECT 1 FROM order_items OI WHERE OI.product_id = P.product_id)),
           COUNT(*)
    FROM products AS P

    UNION ALL

    -- 10. Duplicate customer emails (counts every customer row sharing an email)
    SELECT 10,
           '10_duplicate_customer_emails',
           COUNT(*) FILTER (WHERE email IS NOT NULL AND dup_count > 1),
           COUNT(*)
    FROM (
        SELECT email,
               COUNT(*) OVER (PARTITION BY LOWER(TRIM(email))) AS dup_count
        FROM customers
    ) AS t
)

SELECT check_name,
       failed_rows,
       total_rows,
       ROUND(failed_rows * 100.0 / NULLIF(total_rows, 0), 2) AS fail_pct,
       CASE WHEN failed_rows = 0 THEN 'PASS' ELSE 'FAIL' END AS status
FROM checks
ORDER BY sort_order;
