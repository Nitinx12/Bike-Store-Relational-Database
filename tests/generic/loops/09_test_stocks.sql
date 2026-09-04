-- Dynamic data quality tests for public.stocks (loops checks, raises exception on failure)
DO $do$
DECLARE
    v_checks text[][] := ARRAY[
        ARRAY['composite key not null/unique', $q$SELECT store_id, product_id FROM public.stocks WHERE store_id IS NOT NULL AND product_id IS NOT NULL GROUP BY store_id, product_id HAVING COUNT(*) > 1 UNION ALL SELECT store_id, product_id FROM public.stocks WHERE store_id IS NULL OR product_id IS NULL GROUP BY store_id, product_id$q$],
        ARRAY['store_id references stores', $q$SELECT s.* FROM public.stocks s WHERE s.store_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM public.stores st WHERE st.store_id = s.store_id)$q$],
        ARRAY['product_id references products', $q$SELECT s.* FROM public.stocks s WHERE s.product_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM public.products p WHERE p.product_id = s.product_id)$q$],
        ARRAY['quantity not null/negative', $q$SELECT * FROM public.stocks WHERE quantity IS NULL OR quantity::bigint < 0$q$],
        ARRAY['updated_at valid', $q$SELECT * FROM public.stocks WHERE updated_at IS NULL OR updated_at > CURRENT_TIMESTAMP$q$]
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
        RAISE EXCEPTION 'Data quality FAILED for public.stocks:%', v_fail;
    ELSE
        RAISE NOTICE 'All data quality tests PASSED for public.stocks';
    END IF;
END
$do$;