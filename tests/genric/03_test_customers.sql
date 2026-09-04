-- Dynamic data quality tests for public.customers (loops checks, raises exception on failure)
DO $do$
DECLARE
    v_checks text[][] := ARRAY[
        ARRAY['customer_id not null/unique', $q$SELECT customer_id FROM public.customers WHERE customer_id IS NOT NULL GROUP BY customer_id HAVING COUNT(*) > 1 UNION ALL SELECT customer_id FROM public.customers WHERE customer_id IS NULL GROUP BY customer_id$q$],
        ARRAY['first/last name not null/empty', $q$SELECT * FROM public.customers WHERE first_name IS NULL OR TRIM(first_name) = '' OR last_name IS NULL OR TRIM(last_name) = ''$q$],
        ARRAY['email valid pattern', $q$SELECT * FROM public.customers WHERE email IS NOT NULL AND email !~ '^[^@\s]+@[^@\s]+\.[^@\s]+$'$q$],
        ARRAY['zip_code valid', $q$SELECT * FROM public.customers WHERE zip_code IS NOT NULL AND (zip_code::text !~ '^[0-9]+$' OR LENGTH(zip_code::text) NOT BETWEEN 3 AND 10)$q$],
        ARRAY['updated_at valid', $q$SELECT * FROM public.customers WHERE updated_at IS NULL OR updated_at > CURRENT_TIMESTAMP$q$]
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
        RAISE EXCEPTION 'Data quality FAILED for public.customers:%', v_fail;
    ELSE
        RAISE NOTICE 'All data quality tests PASSED for public.customers';
    END IF;
END
$do$;