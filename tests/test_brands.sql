-- Data quality tests for public.brands
-- Each query should return 0 rows if the table passes the check.

-- Test 1: brand_id must not be null
SELECT *
FROM public.brands
WHERE brand_id IS NULL;

-- Test 2: brand_id must be unique (no duplicates)
SELECT brand_id, COUNT(*) AS cnt
FROM public.brands
GROUP BY brand_id
HAVING COUNT(*) > 1;

-- Test 3: brand_name must not be null or empty
SELECT *
FROM public.brands
WHERE brand_name IS NULL
   OR TRIM(brand_name) = '';

-- Test 4: updated_at must not be null and not in the future
SELECT *
FROM public.brands
WHERE updated_at IS NULL
   OR updated_at > CURRENT_TIMESTAMP;

-- Test 5: brand_id must be a positive number (when stored as text, must be numeric and > 0)
SELECT *
FROM public.brands
WHERE brand_id::text !~ '^[0-9]+$'
   OR brand_id::bigint <= 0;