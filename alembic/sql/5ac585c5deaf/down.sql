ALTER DEFAULT PRIVILEGES FOR ROLE app_user IN SCHEMA sales
    REVOKE SELECT ON TABLES FROM inventory_manager;

REVOKE UPDATE (status, processed_by) ON sales.orders FROM inventory_manager;

REVOKE SELECT ON sales.order_items FROM inventory_manager;
REVOKE SELECT ON sales.orders FROM inventory_manager;

REVOKE USAGE ON SCHEMA sales FROM inventory_manager;

ALTER TABLE sales.orders
DROP COLUMN IF EXISTS processed_by;
