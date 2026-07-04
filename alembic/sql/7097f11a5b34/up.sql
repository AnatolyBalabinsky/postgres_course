CREATE ROLE inventory_manager WITH LOGIN PASSWORD 'inventorymanager';
CREATE ROLE worker WITH LOGIN PASSWORD 'workerpass';

INSERT INTO auth.users (username, password, role)
SELECT 'inventory_manager', crypt('inventorymanager', gen_salt('bf')), 'inventory_manager'
WHERE NOT EXISTS (SELECT 1 FROM auth.users WHERE username = 'inventory_manager');

INSERT INTO auth.users (username, password, role)
SELECT 'worker', crypt('workerpass', gen_salt('bf')), 'worker'
WHERE NOT EXISTS (SELECT 1 FROM auth.users WHERE username = 'worker');
