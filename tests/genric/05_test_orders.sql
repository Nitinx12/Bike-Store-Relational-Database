-- Dynamic data quality tests for public.orders (loops checks, raises exception on failure)
DO $do$
DECLARE
    v_checks text[][] := ARRAY[
        ARRAY['order_id not null/unique', $q$SELECT order_id FROM public.orders WHERE order_id IS NOT NULL GROUP BY order_id HAVING COUNT(*) > 1 UNION ALL SELECT order_id FROM public.orders WHERE order_id IS NULL GROUP BY order_id$q$],
        ARRAY['customer_id references customers', $q$SELECT o.* FROM public.orders o WHERE o.customer_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM public.customers c WHERE c.customer_id = o.customer_id)$q$],
        ARRAY['store_id/staff_id reference stores/staffs', $q$SELECT o.* FROM public.orders o WHERE (o.store_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM public.stores st WHERE st.store_id = o.store_id)) OR (o.staff_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM public.staffs sf WHERE sf.staff_id = o.staff_id))$q$],
        ARRAY['order_status is expected value', $q$SELECT * FROM public.orders WHERE order_status IS NULL OR order_status NOT IN ('Pending', 'Processing', 'Rejected', 'Completed')$q$],
        ARRAY['date logic consistent', $q$SELECT * FROM public.orders WHERE order_date IS NULL OR (required_date IS NOT NULL AND required_date < order_date) OR (shipped_date IS NOT NULL AND shipped_date < order_date)$q$]
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
        RAISE EXCEPTION 'Data quality FAILED for public.orders:%', v_fail;
    ELSE
        RAISE NOTICE 'All data quality tests PASSED for public.orders';
    END IF;
END
$do$;