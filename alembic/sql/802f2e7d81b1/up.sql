CREATE TABLE IF NOT EXISTS catalog.cities (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

INSERT INTO catalog.cities (name) VALUES
    ('Москва'),
    ('Санкт-Петербург'),
    ('Новосибирск'),
    ('Екатеринбург'),
    ('Казань'),
    ('Нижний Новгород'),
    ('Челябинск'),
    ('Самара'),
    ('Омск'),
    ('Ростов-на-Дону'),
    ('Уфа'),
    ('Красноярск'),
    ('Воронеж'),
    ('Пермь'),
    ('Волгоград');

ALTER TABLE catalog.warehouses
ADD COLUMN IF NOT EXISTS city_id INTEGER;

UPDATE catalog.warehouses w
SET city_id = c.id
FROM catalog.cities c
WHERE w.city = c.name;

ALTER TABLE catalog.warehouses
ALTER COLUMN city_id SET NOT NULL;

ALTER TABLE catalog.warehouses
DROP COLUMN IF EXISTS city;

ALTER TABLE catalog.warehouses
ADD CONSTRAINT fk_warehouses_city
FOREIGN KEY (city_id) REFERENCES catalog.cities(id) ON DELETE RESTRICT;
