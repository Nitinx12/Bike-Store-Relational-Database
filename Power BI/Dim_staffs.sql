SELECT 
    s.staff_id,
    CONCAT(s.first_name, ' ', s.last_name) AS staff_name,
    s.email,
    s.active,
    s.store_id,
    CONCAT(m.first_name, ' ', m.last_name) AS manager_name
FROM staffs s
LEFT JOIN staffs m ON s.manager_id = m.staff_id;