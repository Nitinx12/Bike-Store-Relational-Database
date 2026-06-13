-- Data quality tests for public.categories
-- Each query should return 0 rows if the table passes the check.

-- Test 1: category_id must not be null
SELECT *
FROM public.categories
WHERE category_id IS NULL;

-- Test 2: category_id must be unique (no duplicates)
SELECT category_id, COUNT(*) AS cnt
FROM public.categories
GROUP BY category_id
HAVING COUNT(*) > 1;

-- Test 3: category_name must not be null or empty
SELECT *
FROM public.categories
WHERE category_name IS NULL
   OR TRIM(category_name) = '';

-- Test 4: updated_at must not be null and not in the future
SELECT *
FROM public.categories
WHERE updated_at IS NULL
   OR updated_at > CURRENT_TIMESTAMP;

-- Test 5: category_id must be a positive number
SELECT *
FROM public.categories
WHERE category_id::text !~ '^[0-9]+$'
   OR category_id::bigint <= 0;