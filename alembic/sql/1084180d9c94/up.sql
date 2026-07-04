GRANT USAGE ON SCHEMA inventory TO inventory_manager;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA inventory TO inventory_manager;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA inventory TO inventory_manager;

ALTER DEFAULT PRIVILEGES FOR ROLE app_user IN SCHEMA inventory
    GRANT ALL ON TABLES TO inventory_manager;
ALTER DEFAULT PRIVILEGES FOR ROLE app_user IN SCHEMA inventory
    GRANT ALL ON SEQUENCES TO inventory_manager;

GRANT USAGE ON SCHEMA sales TO inventory_manager;
GRANT SELECT ON ALL TABLES IN SCHEMA sales TO inventory_manager;
GRANT UPDATE (status) ON sales.orders TO inventory_manager;

GRANT SELECT ON ALL TABLES IN SCHEMA catalog TO inventory_manager;


GRANT USAGE ON SCHEMA inventory TO worker;

GRANT SELECT, UPDATE ON inventory.stock TO worker;

GRANT SELECT, UPDATE ON inventory.reserves TO worker;

GRANT SELECT, UPDATE (status, shipped_at) ON inventory.deliveries TO worker;
GRANT SELECT, UPDATE (status) ON inventory.delivery_items TO worker;

GRANT SELECT, UPDATE (status, started_at, arriving_at, received_at) ON inventory.transfers TO worker;
GRANT SELECT, UPDATE (status) ON inventory.transfer_items TO worker;

GRANT SELECT ON inventory.routes TO worker;
