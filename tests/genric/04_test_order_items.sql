-- Data quality tests for public.order_items
-- Each query should return 0 rows if the table passes the check.

-- Test 1: composite key (order_id, item_id) must not be null and must be unique
SELECT order_id, item_id, COUNT(*) AS cnt
FROM public.order_items
WHERE order_id IS NOT NULL AND item_id IS NOT NULL
GROUP BY order_id, item_id
HAVING COUNT(*) > 1
UNION ALL
SELECT order_id, item_id, COUNT(*)
FROM public.order_items
WHERE order_id IS NULL OR item_id IS NULL
GROUP BY order_id, item_id;

-- Test 2: order_id must reference an existing order
SELECT oi.*
FROM public.order_items oi
WHERE oi.order_id IS NOT NULL
  AND NOT EXISTS (
      SELECT 1 FROM public.orders o WHERE o.order_id = oi.order_id
  );

-- Test 3: product_id, when present, must reference an existing product
SELECT oi.*
FROM public.order_items oi
WHERE oi.product_id IS NOT NULL
  AND NOT EXISTS (
      SELECT 1 FROM public.products p WHERE p.product_id = oi.product_id
  );

-- Test 4: quantity must be a positive whole number, list_price must be non negative,
-- and discount must be between 0 and 1
SELECT *
FROM public.order_items
WHERE quantity IS NULL
   OR quantity::bigint <= 0
   OR list_price IS NULL
   OR list_price::numeric < 0
   OR discount IS NULL
   OR discount::numeric < 0
   OR discount::numeric > 1;

-- Test 5: generated total_value must match the expected calculation
-- (quantity * list_price * (1 - discount)), allowing a small rounding tolerance
SELECT *
FROM public.order_items
WHERE total_value IS NULL
   OR ABS(
        total_value::numeric
        - (quantity::numeric * list_price::numeric * (1 - discount::numeric))
      ) > 0.01;