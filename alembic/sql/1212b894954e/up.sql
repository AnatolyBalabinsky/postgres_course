CREATE SCHEMA IF NOT EXISTS inventory;

CREATE TABLE inventory.routes (
    from_city_id INTEGER NOT NULL,
    to_city_id INTEGER NOT NULL,
    duration INTERVAL NOT NULL,
    total_threshold DECIMAL(10, 2) NOT NULL CHECK (total_threshold > 0),
    PRIMARY KEY (from_city_id, to_city_id),
    FOREIGN KEY (from_city_id) REFERENCES catalog.cities(id) ON DELETE RESTRICT,
    FOREIGN KEY (to_city_id) REFERENCES catalog.cities(id) ON DELETE RESTRICT,
    CHECK (from_city_id != to_city_id)
);

CREATE TABLE inventory.stock (
    warehouse_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 0 CHECK (quantity >= 0),
    PRIMARY KEY (warehouse_id, product_id),
    FOREIGN KEY (warehouse_id) REFERENCES catalog.warehouses(id) ON DELETE RESTRICT,
    FOREIGN KEY (product_id) REFERENCES catalog.products(id) ON DELETE RESTRICT
);

CREATE TABLE inventory.reserves (
    id SERIAL PRIMARY KEY,
    order_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    FOREIGN KEY (order_id) REFERENCES sales.orders(id) ON DELETE RESTRICT,
    FOREIGN KEY (product_id) REFERENCES catalog.products(id) ON DELETE RESTRICT
);

CREATE TABLE inventory.deliveries (
    order_id INTEGER PRIMARY KEY,
    status VARCHAR(20) NOT NULL DEFAULT 'planned'
        CHECK (status IN ('planned', 'shipping', 'shipped')),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    shipped_at TIMESTAMP,
    FOREIGN KEY (order_id) REFERENCES sales.orders(id) ON DELETE RESTRICT
);

CREATE TABLE inventory.delivery_items (
    order_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    reserve_id INTEGER NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'planned'
        CHECK (status IN ('planned', 'shipped')),
    PRIMARY KEY (order_id, product_id),
    FOREIGN KEY (order_id) REFERENCES inventory.deliveries(order_id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES catalog.products(id) ON DELETE RESTRICT,
    FOREIGN KEY (reserve_id) REFERENCES inventory.reserves(id) ON DELETE RESTRICT
);

CREATE TABLE inventory.transfers (
    id SERIAL PRIMARY KEY,
    from_warehouse_id INTEGER NOT NULL,
    to_warehouse_id INTEGER NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'planned'
        CHECK (status IN ('planned', 'shipping', 'in_transit', 'arrived', 'received')),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    started_at TIMESTAMP,
    arriving_at TIMESTAMP,
    received_at TIMESTAMP,
    FOREIGN KEY (from_warehouse_id) REFERENCES catalog.warehouses(id) ON DELETE RESTRICT,
    FOREIGN KEY (to_warehouse_id) REFERENCES catalog.warehouses(id) ON DELETE RESTRICT,
    CHECK (from_warehouse_id != to_warehouse_id)
);

CREATE TABLE inventory.transfer_items (
    id SERIAL PRIMARY KEY,
    transfer_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    reserve_id INTEGER REFERENCES inventory.reserves(id) ON DELETE RESTRICT,
    requested_by INTEGER NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'planned'
        CHECK (status IN ('planned', 'shipped', 'received')),
    FOREIGN KEY (transfer_id) REFERENCES inventory.transfers(id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES catalog.products(id) ON DELETE RESTRICT,
    FOREIGN KEY (requested_by) REFERENCES auth.users(id) ON DELETE RESTRICT
);
