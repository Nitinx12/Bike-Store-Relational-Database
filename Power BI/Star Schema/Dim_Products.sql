SELECT 
    p.product_id,
    p.product_name,
    p.model_year,
    b.brand_name,
    c.category_name,
    p.list_price AS current_list_price
FROM products p
LEFT JOIN brands b ON p.brand_id = b.brand_id
LEFT JOIN categories c ON p.category_id = c.category_id;