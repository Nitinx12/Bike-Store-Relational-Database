-- Data quality tests for public.products
-- Each query should return 0 rows if the table passes the check.

-- Test 1: product_id must not be null and must be unique
SELECT product_id, COUNT(*) AS cnt
FROM public.products
WHERE product_id IS NOT NULL
GROUP BY product_id
HAVING COUNT(*) > 1
UNION ALL
SELECT product_id, COUNT(*)
FROM public.products
WHERE product_id IS NULL
GROUP BY product_id;

-- Test 2: product_name must not be null or empty
SELECT *
FROM public.products
WHERE product_name IS NULL
   OR TRIM(product_name) = '';

-- Test 3: brand_id, when present, must reference an existing brand
SELECT p.*
FROM public.products p
WHERE p.brand_id IS NOT NULL
  AND NOT EXISTS (
      SELECT 1 FROM public.brands b WHERE b.brand_id = p.brand_id
  );

-- Test 4: category_id, when present, must reference an existing category
SELECT p.*
FROM public.products p
WHERE p.category_id IS NOT NULL
  AND NOT EXISTS (
      SELECT 1 FROM public.categories c WHERE c.category_id = p.category_id
  );

-- Test 5: list_price must be numeric, non negative, and model_year must be a
-- reasonable 4 digit year (1900 to next calendar year)
SELECT *
FROM public.products
WHERE list_price IS NULL
   OR list_price::numeric < 0
   OR model_year IS NULL
   OR model_year::bigint < 1900
   OR model_year::bigint > EXTRACT(YEAR FROM CURRENT_DATE)::bigint + 1;