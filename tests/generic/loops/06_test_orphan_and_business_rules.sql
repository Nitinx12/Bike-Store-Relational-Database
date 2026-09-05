-- Dynamic orphan-row and business-rule tests across the schema (loops checks, raises exception on failure)
DO $do$
DECLARE
    v_checks text[][] := ARRAY[
        ARRAY['orphan_orders_customer', $q$SELECT o.* FROM public.orders o WHERE o.customer_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM public.customers c WHERE c.customer_id = o.customer_id)$q$],
        ARRAY['orphan_orders_staff', $q$SELECT o.* FROM public.orders o WHERE o.staff_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM public.staffs s WHERE s.staff_id = o.staff_id)$q$],
        ARRAY['orphan_orders_store', $q$SELECT o.* FROM public.orders o WHERE o.store_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM public.stores st WHERE st.store_id = o.store_id)$q$],
        ARRAY['orphan_order_items_order', $q$SELECT oi.* FROM public.order_items oi WHERE oi.order_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM public.orders o WHERE o.order_id = oi.order_id)$q$],
        ARRAY['orphan_order_items_product', $q$SELECT oi.* FROM public.order_items oi WHERE oi.product_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM public.products p WHERE p.product_id = oi.product_id)$q$],
        ARRAY['orphan_products_brand', $q$SELECT p.* FROM public.products p WHERE p.brand_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM public.brands b WHERE b.brand_id = p.brand_id)$q$],
        ARRAY['orphan_products_category', $q$SELECT p.* FROM public.products p WHERE p.category_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM public.categories c WHERE c.category_id = p.category_id)$q$],
        ARRAY['orphan_staffs_store', $q$SELECT s.* FROM public.staffs s WHERE s.store_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM public.stores st WHERE st.store_id = s.store_id)$q$],
        ARRAY['orphan_staffs_manager', $q$SELECT s.* FROM public.staffs s WHERE s.manager_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM public.staffs m WHERE m.staff_id = s.manager_id)$q$],
        ARRAY['orphan_stocks_store_or_product', $q$SELECT st.* FROM public.stocks st WHERE (st.store_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM public.stores s WHERE s.store_id = st.store_id)) OR (st.product_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM public.products p WHERE p.product_id = st.product_id))$q$],
        ARRAY['business_order_with_no_items', $q$SELECT o.order_id FROM public.orders o WHERE NOT EXISTS (SELECT 1 FROM public.order_items oi WHERE oi.order_id = o.order_id)$q$],
        ARRAY['business_shipped_order_missing_or_future_date', $q$SELECT o.* FROM public.orders o WHERE o.order_status IN ('shipped', 'delivered') AND (o.shipped_date IS NULL OR o.shipped_date::date > CURRENT_DATE)$q$],
        ARRAY['business_unshipped_order_has_shipped_date', $q$SELECT o.* FROM public.orders o WHERE o.order_status IN ('pending', 'processing') AND o.shipped_date IS NOT NULL$q$],
        ARRAY['business_staff_store_mismatch', $q$SELECT o.* FROM public.orders o JOIN public.staffs s ON s.staff_id = o.staff_id WHERE o.store_id IS NOT NULL AND s.store_id IS NOT NULL AND o.store_id <> s.store_id$q$],
        ARRAY['business_stock_quantity_outlier', $q$SELECT s.* FROM public.stocks s WHERE s.quantity::bigint > 100000$q$],
        ARRAY['business_order_item_price_mismatch', $q$SELECT oi.order_id, oi.item_id, oi.product_id, oi.list_price AS item_price, p.list_price AS product_price FROM public.order_items oi JOIN public.products p ON p.product_id = oi.product_id WHERE p.list_price::numeric > 0 AND ABS(oi.list_price::numeric - p.list_price::numeric) / p.list_price::numeric > 0.5$q$],
        ARRAY['business_inactive_staff_with_orders', $q$SELECT o.* FROM public.orders o JOIN public.staffs s ON s.staff_id = o.staff_id WHERE s.active::bigint = 0$q$],
        ARRAY['business_order_total_zero_or_negative', $q$SELECT oi.order_id, SUM(oi.total_value::numeric) AS order_total FROM public.order_items oi GROUP BY oi.order_id HAVING SUM(oi.total_value::numeric) <= 0$q$],
        ARRAY['business_active_product_missing_price', $q$SELECT p.* FROM public.products p WHERE (p.list_price IS NULL OR p.list_price::numeric <= 0) AND (EXISTS (SELECT 1 FROM public.order_items oi WHERE oi.product_id = p.product_id) OR EXISTS (SELECT 1 FROM public.stocks st WHERE st.product_id = p.product_id))$q$]
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
        RAISE EXCEPTION 'Orphan/business rule checks FAILED:%', v_fail;
    ELSE
        RAISE NOTICE 'All orphan/business rule checks PASSED';
    END IF;
END
$do$;