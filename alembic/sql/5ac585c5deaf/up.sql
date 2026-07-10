ALTER TABLE sales.orders
ADD COLUMN IF NOT EXISTS processed_by INTEGER
REFERENCES auth.users(id) ON DELETE SET NULL;

GRANT USAGE ON SCHEMA sales TO inventory_manager;

GRANT SELECT ON sales.orders TO inventory_manager;
GRANT SELECT ON sales.order_items TO inventory_manager;

GRANT UPDATE (status, processed_by) ON sales.orders TO inventory_manager;
