-- Data quality tests for public.stores
-- Each query should return 0 rows if the table passes the check.

-- Test 1: store_id must not be null and must be unique
SELECT store_id, COUNT(*) AS cnt
FROM public.stores
WHERE store_id IS NOT NULL
GROUP BY store_id
HAVING COUNT(*) > 1
UNION ALL
SELECT store_id, COUNT(*)
FROM public.stores
WHERE store_id IS NULL
GROUP BY store_id;

-- Test 2: store_name must not be null or empty
SELECT *
FROM public.stores
WHERE store_name IS NULL
   OR TRIM(store_name) = '';

-- Test 3: email must follow a basic valid email pattern when present
SELECT *
FROM public.stores
WHERE email IS NOT NULL
  AND email !~ '^[^@\s]+@[^@\s]+\.[^@\s]+$';

-- Test 4: zip_code must be numeric and a reasonable length (3 to 10 digits) when present
SELECT *
FROM public.stores
WHERE zip_code IS NOT NULL
  AND (zip_code::text !~ '^[0-9]+$'
       OR LENGTH(zip_code::text) NOT BETWEEN 3 AND 10);

-- Test 5: updated_at must not be null and not in the future
SELECT *
FROM public.stores
WHERE updated_at IS NULL
   OR updated_at > CURRENT_TIMESTAMP;