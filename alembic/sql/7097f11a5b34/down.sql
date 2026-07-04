DELETE FROM auth.users WHERE username = 'inventory_manager';
DELETE FROM auth.users WHERE username = 'worker';

DROP ROLE IF EXISTS inventory_manager;
DROP ROLE IF EXISTS worker;
