-- Data quality tests for public.orders
-- Each query should return 0 rows if the table passes the check.

-- Test 1: order_id must not be null and must be unique
SELECT order_id, COUNT(*) AS cnt
FROM public.orders
WHERE order_id IS NOT NULL
GROUP BY order_id
HAVING COUNT(*) > 1
UNION ALL
SELECT order_id, COUNT(*)
FROM public.orders
WHERE order_id IS NULL
GROUP BY order_id;

-- Test 2: customer_id, when present, must reference an existing customer
SELECT o.*
FROM public.orders o
WHERE o.customer_id IS NOT NULL
  AND NOT EXISTS (
      SELECT 1 FROM public.customers c WHERE c.customer_id = o.customer_id
  );

-- Test 3: store_id and staff_id, when present, must reference existing stores and staff
SELECT o.*
FROM public.orders o
WHERE (o.store_id IS NOT NULL
       AND NOT EXISTS (SELECT 1 FROM public.stores st WHERE st.store_id = o.store_id))
   OR (o.staff_id IS NOT NULL
       AND NOT EXISTS (SELECT 1 FROM public.staffs sf WHERE sf.staff_id = o.staff_id));

-- Test 4: order_status must be one of the expected values
SELECT *
FROM public.orders
WHERE order_status IS NULL
   OR order_status NOT IN ('pending', 'processing', 'rejected', 'completed', 'cancelled', 'shipped', 'delivered');

-- Test 5: date logic must be consistent
-- order_date must not be null, required_date must not be before order_date,
-- and shipped_date (when present) must not be before order_date
SELECT *
FROM public.orders
WHERE order_date IS NULL
   OR (required_date IS NOT NULL AND required_date < order_date)
   OR (shipped_date  IS NOT NULL AND shipped_date  < order_date);