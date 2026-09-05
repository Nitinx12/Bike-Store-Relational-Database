-- Dynamic data quality tests for public.stores (loops checks, raises exception on failure)
DO $do$
DECLARE
    v_checks text[][] := ARRAY[
        ARRAY['store_id not null/unique', $q$SELECT store_id FROM public.stores WHERE store_id IS NOT NULL GROUP BY store_id HAVING COUNT(*) > 1 UNION ALL SELECT store_id FROM public.stores WHERE store_id IS NULL GROUP BY store_id$q$],
        ARRAY['store_name not null/empty', $q$SELECT * FROM public.stores WHERE store_name IS NULL OR TRIM(store_name) = ''$q$],
        ARRAY['email valid pattern', $q$SELECT * FROM public.stores WHERE email IS NOT NULL AND email !~ '^[^@\s]+@[^@\s]+\.[^@\s]+$'$q$],
        ARRAY['zip_code valid', $q$SELECT * FROM public.stores WHERE zip_code IS NOT NULL AND (zip_code::text !~ '^[0-9]+$' OR LENGTH(zip_code::text) NOT BETWEEN 3 AND 10)$q$],
        ARRAY['updated_at valid', $q$SELECT * FROM public.stores WHERE updated_at IS NULL OR updated_at::timestamptz > CURRENT_TIMESTAMP$q$]
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
        RAISE EXCEPTION 'Data quality FAILED for public.stores:%', v_fail;
    ELSE
        RAISE NOTICE 'All data quality tests PASSED for public.stores';
    END IF;
END
$do$;