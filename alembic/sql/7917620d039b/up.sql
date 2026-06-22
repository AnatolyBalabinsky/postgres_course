ALTER TABLE sales.orders ADD COLUMN IF NOT EXISTS created_by INTEGER;

INSERT INTO auth.users (username, password, role)
SELECT 'system', crypt('system_migration', gen_salt('bf')), 'sales_manager'
WHERE NOT EXISTS (SELECT 1 FROM auth.users WHERE username = 'system');

UPDATE sales.orders
SET created_by = (SELECT id FROM auth.users WHERE username = 'system')
WHERE created_by IS NULL;

ALTER TABLE sales.orders ALTER COLUMN created_by SET NOT NULL;

ALTER TABLE sales.orders
    ADD CONSTRAINT fk_orders_created_by
    FOREIGN KEY (created_by) REFERENCES auth.users(id) ON DELETE RESTRICT;
