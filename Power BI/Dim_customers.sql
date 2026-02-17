SELECT 
    customer_id,
    first_name,
    last_name,
    CONCAT(first_name, ' ', last_name) AS full_name,
    email,
    phone,
    city,
    state,
    zip_code,
    CONCAT(city, ', ', state) AS location_ke
FROM customers;