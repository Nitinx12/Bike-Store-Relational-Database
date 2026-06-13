-- Final data quality tests: orphan rows and business logic validation
-- Cross table checks across the full retail schema.
-- Each query should return 0 rows if the dataset passes the check.

-- ═══════════════════════════════════════════════════════════════════════
-- SECTION 1: ORPHAN ROW CHECKS
-- An orphan row is a child row whose foreign key value does not exist
-- in the parent table.
-- ═══════════════════════════════════════════════════════════════════════

-- Orphan 1: orders with a customer_id that does not exist in customers
SELECT 'orphan_orders_customer' AS check_name, o.*
FROM public.orders o
WHERE o.customer_id IS NOT NULL
  AND NOT EXISTS (
      SELECT 1 FROM public.customers c WHERE c.customer_id = o.customer_id
  );

-- Orphan 2: orders with a staff_id that does not exist in staffs
SELECT 'orphan_orders_staff' AS check_name, o.*
FROM public.orders o
WHERE o.staff_id IS NOT NULL
  AND NOT EXISTS (
      SELECT 1 FROM public.staffs s WHERE s.staff_id = o.staff_id
  );

-- Orphan 3: orders with a store_id that does not exist in stores
SELECT 'orphan_orders_store' AS check_name, o.*
FROM public.orders o
WHERE o.store_id IS NOT NULL
  AND NOT EXISTS (
      SELECT 1 FROM public.stores st WHERE st.store_id = o.store_id
  );

-- Orphan 4: order_items with an order_id that does not exist in orders
SELECT 'orphan_order_items_order' AS check_name, oi.*
FROM public.order_items oi
WHERE oi.order_id IS NOT NULL
  AND NOT EXISTS (
      SELECT 1 FROM public.orders o WHERE o.order_id = oi.order_id
  );

-- Orphan 5: order_items with a product_id that does not exist in products
SELECT 'orphan_order_items_product' AS check_name, oi.*
FROM public.order_items oi
WHERE oi.product_id IS NOT NULL
  AND NOT EXISTS (
      SELECT 1 FROM public.products p WHERE p.product_id = oi.product_id
  );

-- Orphan 6: products with a brand_id that does not exist in brands
SELECT 'orphan_products_brand' AS check_name, p.*
FROM public.products p
WHERE p.brand_id IS NOT NULL
  AND NOT EXISTS (
      SELECT 1 FROM public.brands b WHERE b.brand_id = p.brand_id
  );

-- Orphan 7: products with a category_id that does not exist in categories
SELECT 'orphan_products_category' AS check_name, p.*
FROM public.products p
WHERE p.category_id IS NOT NULL
  AND NOT EXISTS (
      SELECT 1 FROM public.categories c WHERE c.category_id = p.category_id
  );

-- Orphan 8: staffs with a store_id that does not exist in stores
SELECT 'orphan_staffs_store' AS check_name, s.*
FROM public.staffs s
WHERE s.store_id IS NOT NULL
  AND NOT EXISTS (
      SELECT 1 FROM public.stores st WHERE st.store_id = s.store_id
  );

-- Orphan 9: staffs with a manager_id that does not exist in staffs
SELECT 'orphan_staffs_manager' AS check_name, s.*
FROM public.staffs s
WHERE s.manager_id IS NOT NULL
  AND NOT EXISTS (
      SELECT 1 FROM public.staffs m WHERE m.staff_id = s.manager_id
  );

-- Orphan 10: stocks with a store_id that does not exist in stores,
-- or a product_id that does not exist in products
SELECT 'orphan_stocks_store_or_product' AS check_name, st.*
FROM public.stocks st
WHERE (st.store_id IS NOT NULL
       AND NOT EXISTS (SELECT 1 FROM public.stores s WHERE s.store_id = st.store_id))
   OR (st.product_id IS NOT NULL
       AND NOT EXISTS (SELECT 1 FROM public.products p WHERE p.product_id = st.product_id));


-- ═══════════════════════════════════════════════════════════════════════
-- SECTION 2: BUSINESS LOGIC VALIDATION
-- These checks validate that the data makes sense from a business
-- perspective, not just structurally.
-- ═══════════════════════════════════════════════════════════════════════

-- Business 1: every order must have at least one order_item.
-- An order with zero line items is likely incomplete or corrupted.
SELECT 'business_order_with_no_items' AS check_name, o.order_id
FROM public.orders o
WHERE NOT EXISTS (
    SELECT 1 FROM public.order_items oi WHERE oi.order_id = o.order_id
);

-- Business 2: a delivered or shipped order must have a shipped_date,
-- and shipped_date must not be in the future.
SELECT 'business_shipped_order_missing_or_future_date' AS check_name, o.*
FROM public.orders o
WHERE o.order_status IN ('shipped', 'delivered')
  AND (o.shipped_date IS NULL
       OR o.shipped_date > CURRENT_DATE);

-- Business 3: a pending or processing order should not already have a
-- shipped_date set.
SELECT 'business_unshipped_order_has_shipped_date' AS check_name, o.*
FROM public.orders o
WHERE o.order_status IN ('pending', 'processing')
  AND o.shipped_date IS NOT NULL;

-- Business 4: the staff member handling an order should belong to the
-- same store that is fulfilling the order.
SELECT 'business_staff_store_mismatch' AS check_name, o.*
FROM public.orders o
JOIN public.staffs s ON s.staff_id = o.staff_id
WHERE o.store_id IS NOT NULL
  AND s.store_id IS NOT NULL
  AND o.store_id <> s.store_id;

-- Business 5: stock quantity for any store and product combination should
-- not be unreasonably high (sanity threshold), flagging likely data entry
-- errors. Adjust the threshold to match expected inventory levels.
SELECT 'business_stock_quantity_outlier' AS check_name, s.*
FROM public.stocks s
WHERE s.quantity::bigint > 100000;

-- Business 6: an order_item's list_price should be reasonably close to the
-- product's current list_price (within 50 percent), flagging line items
-- that may have been recorded with the wrong price.
SELECT 'business_order_item_price_mismatch' AS check_name, oi.order_id, oi.item_id, oi.product_id,
       oi.list_price AS item_price, p.list_price AS product_price
FROM public.order_items oi
JOIN public.products p ON p.product_id = oi.product_id
WHERE p.list_price::numeric > 0
  AND ABS(oi.list_price::numeric - p.list_price::numeric) / p.list_price::numeric > 0.5;

-- Business 7: an inactive staff member should not be assigned to handle
-- any order placed after they became inactive (proxy check: any order at all
-- assigned to an inactive staff member).
SELECT 'business_inactive_staff_with_orders' AS check_name, o.*
FROM public.orders o
JOIN public.staffs s ON s.staff_id = o.staff_id
WHERE s.active::bigint = 0;

-- Business 8: required_date should generally be after order_date by at
-- least one day (an order required on the same day it was placed is
-- unusual and worth flagging).
SELECT 'business_order_required_same_day' AS check_name, o.*
FROM public.orders o
WHERE o.required_date IS NOT NULL
  AND o.required_date = o.order_date;

-- Business 9: total_value for an order (sum of its order_items) should
-- not be zero or negative, which would indicate a fully discounted or
-- corrupted order.
SELECT 'business_order_total_zero_or_negative' AS check_name, oi.order_id,
       SUM(oi.total_value::numeric) AS order_total
FROM public.order_items oi
GROUP BY oi.order_id
HAVING SUM(oi.total_value::numeric) <= 0;

-- Business 10: every product that appears in order_items or stocks should
-- have a non null, positive list_price. A product priced at zero or null
-- but actively sold or stocked is a likely data issue.
SELECT 'business_active_product_missing_price' AS check_name, p.*
FROM public.products p
WHERE (p.list_price IS NULL OR p.list_price::numeric <= 0)
  AND (
      EXISTS (SELECT 1 FROM public.order_items oi WHERE oi.product_id = p.product_id)
      OR EXISTS (SELECT 1 FROM public.stocks st WHERE st.product_id = p.product_id)
  );