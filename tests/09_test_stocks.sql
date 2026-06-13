-- Data quality tests for public.stocks
-- Each query should return 0 rows if the table passes the check.

-- Test 1: composite key (store_id, product_id) must not be null and must be unique
SELECT store_id, product_id, COUNT(*) AS cnt
FROM public.stocks
WHERE store_id IS NOT NULL AND product_id IS NOT NULL
GROUP BY store_id, product_id
HAVING COUNT(*) > 1
UNION ALL
SELECT store_id, product_id, COUNT(*)
FROM public.stocks
WHERE store_id IS NULL OR product_id IS NULL
GROUP BY store_id, product_id;

-- Test 2: store_id must reference an existing store
SELECT s.*
FROM public.stocks s
WHERE s.store_id IS NOT NULL
  AND NOT EXISTS (
      SELECT 1 FROM public.stores st WHERE st.store_id = s.store_id
  );

-- Test 3: product_id must reference an existing product
SELECT s.*
FROM public.stocks s
WHERE s.product_id IS NOT NULL
  AND NOT EXISTS (
      SELECT 1 FROM public.products p WHERE p.product_id = s.product_id
  );

-- Test 4: quantity must not be null and must not be negative
SELECT *
FROM public.stocks
WHERE quantity IS NULL
   OR quantity::bigint < 0;

-- Test 5: updated_at must not be null and not in the future
SELECT *
FROM public.stocks
WHERE updated_at IS NULL
   OR updated_at > CURRENT_TIMESTAMP;