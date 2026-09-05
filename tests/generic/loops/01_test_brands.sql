-- Dynamic data quality tests for public.brands (loops checks, raises exception on failure)
DO $do$
DECLARE
    v_checks text[][] := ARRAY[
        ARRAY['brand_id not null', $q$SELECT * FROM public.brands WHERE brand_id IS NULL$q$],
        ARRAY['brand_id unique', $q$SELECT brand_id FROM public.brands GROUP BY brand_id HAVING COUNT(*) > 1$q$],
        ARRAY['brand_name not null/empty', $q$SELECT * FROM public.brands WHERE brand_name IS NULL OR TRIM(brand_name) = ''$q$],
        ARRAY['updated_at valid', $q$SELECT * FROM public.brands WHERE updated_at IS NULL OR updated_at::timestamptz > CURRENT_TIMESTAMP$q$],
        ARRAY['brand_id positive numeric', $q$SELECT * FROM public.brands WHERE brand_id::text !~ '^[0-9]+$' OR brand_id::bigint <= 0$q$]
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
        RAISE EXCEPTION 'Data quality FAILED for public.brands:%', v_fail;
    ELSE
        RAISE NOTICE 'All data quality tests PASSED for public.brands';
    END IF;
END
$do$;