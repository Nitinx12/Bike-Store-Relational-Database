-- Dynamic data quality tests for public.staffs (loops checks, raises exception on failure)
DO $do$
DECLARE
    v_checks text[][] := ARRAY[
        ARRAY['staff_id not null/unique', $q$SELECT staff_id FROM public.staffs WHERE staff_id IS NOT NULL GROUP BY staff_id HAVING COUNT(*) > 1 UNION ALL SELECT staff_id FROM public.staffs WHERE staff_id IS NULL GROUP BY staff_id$q$],
        ARRAY['first/last name not null/empty', $q$SELECT * FROM public.staffs WHERE first_name IS NULL OR TRIM(first_name) = '' OR last_name IS NULL OR TRIM(last_name) = ''$q$],
        ARRAY['store_id references stores', $q$SELECT s.* FROM public.staffs s WHERE s.store_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM public.stores st WHERE st.store_id = s.store_id)$q$],
        ARRAY['manager_id valid, no self-management', $q$SELECT s.* FROM public.staffs s WHERE s.manager_id IS NOT NULL AND (s.manager_id = s.staff_id OR NOT EXISTS (SELECT 1 FROM public.staffs m WHERE m.staff_id = s.manager_id))$q$],
        ARRAY['active/updated_at valid', $q$SELECT * FROM public.staffs WHERE active IS NULL OR active::integer NOT IN (0, 1) OR updated_at IS NULL OR updated_at::timestamptz > CURRENT_TIMESTAMP$q$]
    ];
    v_name  text;
    v_query text;
    v_count int;
    v_fail  text := '';
BEGIN
    FOR i IN 1..array_length(v_checks, 1) LOOP
        v_name  := v_checks[i][1];
        v_query := v_checks[i][2];
        EXECUTE format('SELECT COUNT(*) FROM (%s) sub', v_query) INTO v_count;
        IF v_count > 0 THEN
            v_fail := v_fail || format(E'\n  - %s: %s row(s)', v_name, v_count);
        END IF;
    END LOOP;

    IF v_fail <> '' THEN
        RAISE EXCEPTION 'Data quality FAILED for public.staffs:%', v_fail;
    ELSE
        RAISE NOTICE 'All data quality tests PASSED for public.staffs';
    END IF;
END
$do$;