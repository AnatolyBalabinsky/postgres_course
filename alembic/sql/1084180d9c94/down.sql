ALTER DEFAULT PRIVILEGES FOR ROLE app_user IN SCHEMA inventory
    REVOKE ALL ON TABLES FROM inventory_manager;
ALTER DEFAULT PRIVILEGES FOR ROLE app_user IN SCHEMA inventory
    REVOKE ALL ON SEQUENCES FROM inventory_manager;

REVOKE ALL ON ALL TABLES IN SCHEMA inventory FROM inventory_manager;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA inventory FROM inventory_manager;
REVOKE USAGE ON SCHEMA inventory FROM inventory_manager;

REVOKE USAGE ON SCHEMA sales FROM inventory_manager;

REVOKE ALL ON inventory.stock FROM worker;
REVOKE ALL ON inventory.reserves FROM worker;
REVOKE ALL ON inventory.deliveries FROM worker;
REVOKE ALL ON inventory.delivery_items FROM worker;
REVOKE ALL ON inventory.transfers FROM worker;
REVOKE ALL ON inventory.transfer_items FROM worker;
REVOKE ALL ON inventory.routes FROM worker;
REVOKE USAGE ON SCHEMA inventory FROM worker;
