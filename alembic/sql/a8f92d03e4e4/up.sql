GRANT USAGE ON SCHEMA sales TO worker;
GRANT SELECT ON ALL TABLES IN SCHEMA sales TO worker;
GRANT UPDATE (status) ON sales.orders TO worker;
