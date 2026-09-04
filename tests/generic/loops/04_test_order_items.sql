-- Dynamic data quality tests for public.order_items (loops checks, raises exception on failure)
DO $do$
DECLARE
    v_checks text[][] := ARRAY[
        ARRAY['composite key not null/unique', $q$SELECT order_id, item_id FROM public.order_items WHERE order_id IS NOT NULL AND item_id IS NOT NULL GROUP BY order_id, item_id HAVING COUNT(*) > 1 UNION ALL SELECT order_id, item_id FROM public.order_items WHERE order_id IS NULL OR item_id IS NULL GROUP BY order_id, item_id$q$],
        ARRAY['order_id references orders', $q$SELECT oi.* FROM public.order_items oi WHERE oi.order_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM public.orders o WHERE o.order_id = oi.order_id)$q$],
        ARRAY['product_id references products', $q$SELECT oi.* FROM public.order_items oi WHERE oi.product_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM public.products p WHERE p.product_id = oi.product_id)$q$],
        ARRAY['quantity/list_price/discount valid', $q$SELECT * FROM public.order_items WHERE quantity IS NULL OR quantity::bigint <= 0 OR list_price IS NULL OR list_price::numeric < 0 OR discount IS NULL OR discount::numeric < 0 OR discount::numeric > 1$q$],
        ARRAY['total_value matches calculation', $q$SELECT * FROM public.order_items WHERE total_value IS NULL OR ABS(total_value::numeric - (quantity::numeric * list_price::numeric * (1 - discount::numeric))) > 0.01$q$]
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
        RAISE EXCEPTION 'Data quality FAILED for public.order_items:%', v_fail;
    ELSE
        RAISE NOTICE 'All data quality tests PASSED for public.order_items';
    END IF;
END
$do$;