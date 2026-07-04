REVOKE UPDATE (status) ON sales.orders FROM worker;
REVOKE ALL ON ALL TABLES IN SCHEMA sales FROM worker;
REVOKE USAGE ON SCHEMA sales FROM worker;
