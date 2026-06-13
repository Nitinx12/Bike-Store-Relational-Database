-- Data quality tests for public.customers
-- Each query should return 0 rows if the table passes the check.

-- Test 1: customer_id must not be null and must be unique
SELECT customer_id, COUNT(*) AS cnt
FROM public.customers
WHERE customer_id IS NOT NULL
GROUP BY customer_id
HAVING COUNT(*) > 1
UNION ALL
SELECT customer_id, COUNT(*)
FROM public.customers
WHERE customer_id IS NULL
GROUP BY customer_id;

-- Test 2: first_name and last_name must not be null or empty
SELECT *
FROM public.customers
WHERE first_name IS NULL OR TRIM(first_name) = ''
   OR last_name  IS NULL OR TRIM(last_name)  = '';

-- Test 3: email must follow a basic valid email pattern when present
SELECT *
FROM public.customers
WHERE email IS NOT NULL
  AND email !~ '^[^@\s]+@[^@\s]+\.[^@\s]+$';

-- Test 4: zip_code must be numeric and a reasonable length (3 to 10 digits) when present
SELECT *
FROM public.customers
WHERE zip_code IS NOT NULL
  AND (zip_code::text !~ '^[0-9]+$'
       OR LENGTH(zip_code::text) NOT BETWEEN 3 AND 10);

-- Test 5: updated_at must not be null and not in the future
SELECT *
FROM public.customers
WHERE updated_at IS NULL
   OR updated_at > CURRENT_TIMESTAMP;