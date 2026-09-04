-- Dynamic data quality tests for public.products (loops checks, raises exception on failure)
DO $do$
DECLARE
    v_checks text[][] := ARRAY[
        ARRAY['product_id not null/unique', $q$SELECT product_id FROM public.products WHERE product_id IS NOT NULL GROUP BY product_id HAVING COUNT(*) > 1 UNION ALL SELECT product_id FROM public.products WHERE product_id IS NULL GROUP BY product_id$q$],
        ARRAY['product_name not null/empty', $q$SELECT * FROM public.products WHERE product_name IS NULL OR TRIM(product_name) = ''$q$],
        ARRAY['brand_id references brands', $q$SELECT p.* FROM public.products p WHERE p.brand_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM public.brands b WHERE b.brand_id = p.brand_id)$q$],
        ARRAY['category_id references categories', $q$SELECT p.* FROM public.products p WHERE p.category_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM public.categories c WHERE c.category_id = p.category_id)$q$],
        ARRAY['list_price/model_year valid', $q$SELECT * FROM public.products WHERE list_price IS NULL OR list_price::numeric < 0 OR model_year IS NULL OR model_year::bigint < 1900 OR model_year::bigint > EXTRACT(YEAR FROM CURRENT_DATE)::bigint + 1$q$]
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
        RAISE EXCEPTION 'Data quality FAILED for public.products:%', v_fail;
    ELSE
        RAISE NOTICE 'All data quality tests PASSED for public.products';
    END IF;
END
$do$;