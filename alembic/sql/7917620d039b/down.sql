ALTER TABLE sales.orders DROP CONSTRAINT IF EXISTS fk_orders_created_by;
ALTER TABLE sales.orders DROP COLUMN IF EXISTS created_by;
DELETE FROM auth.users WHERE username = 'system';
