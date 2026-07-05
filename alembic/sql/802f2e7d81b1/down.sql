ALTER TABLE catalog.warehouses
ADD COLUMN IF NOT EXISTS city TEXT;

UPDATE catalog.warehouses w
SET city = c.name
FROM catalog.cities c
WHERE w.city_id = c.id;

ALTER TABLE catalog.warehouses
DROP CONSTRAINT fk_warehouses_city;

ALTER TABLE catalog.warehouses
DROP COLUMN IF EXISTS city_id;

ALTER TABLE catalog.warehouses
ALTER COLUMN city SET NOT NULL;

DROP TABLE IF EXISTS catalog.cities;
