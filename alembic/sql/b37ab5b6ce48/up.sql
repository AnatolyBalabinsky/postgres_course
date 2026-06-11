CREATE SCHEMA IF NOT EXISTS sales;

CREATE TABLE IF NOT EXISTS sales.orders (
    id serial PRIMARY KEY,
    status VARCHAR(20) NOT NULL DEFAULT 'unpublished'
        CHECK (status IN ('unpublished', 'new', 'processing', 'pending', 'packing', 'shipped')),
    total_amount DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    warehouse_id INTEGER NOT NULL REFERENCES catalog.warehouses(id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS sales.order_items (
    id serial PRIMARY KEY,
    order_id INTEGER NOT NULL REFERENCES sales.orders(id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES catalog.products(id) ON DELETE RESTRICT,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    price DECIMAL(10, 2) NOT NULL,
    UNIQUE (order_id, product_id)
);
