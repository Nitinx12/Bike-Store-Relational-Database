-- Data quality tests for public.staffs
-- Each query should return 0 rows if the table passes the check.

-- Test 1: staff_id must not be null and must be unique
SELECT staff_id, COUNT(*) AS cnt
FROM public.staffs
WHERE staff_id IS NOT NULL
GROUP BY staff_id
HAVING COUNT(*) > 1
UNION ALL
SELECT staff_id, COUNT(*)
FROM public.staffs
WHERE staff_id IS NULL
GROUP BY staff_id;

-- Test 2: first_name and last_name must not be null or empty
SELECT *
FROM public.staffs
WHERE first_name IS NULL OR TRIM(first_name) = ''
   OR last_name  IS NULL OR TRIM(last_name)  = '';

-- Test 3: store_id must reference an existing store (referential integrity)
SELECT s.*
FROM public.staffs s
WHERE s.store_id IS NOT NULL
  AND NOT EXISTS (
      SELECT 1 FROM public.stores st WHERE st.store_id = s.store_id
  );

-- Test 4: manager_id, when present, must reference an existing staff member
-- and must not be equal to the staff member's own staff_id (no self-management)
SELECT s.*
FROM public.staffs s
WHERE s.manager_id IS NOT NULL
  AND (
      s.manager_id = s.staff_id
      OR NOT EXISTS (
          SELECT 1 FROM public.staffs m WHERE m.staff_id = s.manager_id
      )
  );

-- Test 5: active must be either 0 or 1, and updated_at must not be null or in the future
SELECT *
FROM public.staffs
WHERE active IS NULL
   OR active NOT IN (0, 1)
   OR updated_at IS NULL
   OR updated_at > CURRENT_TIMESTAMP;