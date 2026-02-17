SELECT
    oi.order_id,
    oi.item_id,
    oi.product_id,
    o.customer_id,
    o.store_id,
    o.staff_id,
    o.order_date,
    o.required_date,
    o.shipped_date,
    oi.quantity,
    oi.list_price AS unit_price,
    oi.discount,
    (oi.quantity * oi.list_price) AS gross_amount,
    (oi.quantity * oi.list_price * oi.discount) AS discount_amount,
    (oi.quantity * oi.list_price * (1 - oi.discount)) AS net_revenue,
    o.order_status
FROM order_items oi
INNER JOIN orders o ON oi.order_id = o.order_id;