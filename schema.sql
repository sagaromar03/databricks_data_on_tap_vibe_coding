-- Data on Tap — Pizza Ordering App :: schema
-- Lakebase (Postgres). Run once to (re)create all tables.
-- Drop order respects FK dependencies: children before parents.

DROP TABLE IF EXISTS order_items;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS inventory;
DROP TABLE IF EXISTS delivery_partners;
DROP TABLE IF EXISTS customers;
DROP TABLE IF EXISTS menu;
DROP TABLE IF EXISTS branches;

-- 1. branches — the locations (multiple branches per city; city is an attribute)
CREATE TABLE branches (
    branch_id    SERIAL PRIMARY KEY,
    branch_name  TEXT NOT NULL,
    city         TEXT NOT NULL,
    address      TEXT,
    latitude     NUMERIC(9,6),        -- nullable; reserved for event-day geo
    longitude    NUMERIC(9,6)         -- nullable; reserved for event-day geo
);

-- 2. customers — first-class; email + password_hash back the login flow
CREATE TABLE customers (
    customer_id   SERIAL PRIMARY KEY,
    name          TEXT NOT NULL,
    email         TEXT NOT NULL UNIQUE,        -- lowercased on signup; the login handle
    phone         TEXT,
    password_hash TEXT,                        -- pbkdf2_sha256$iter$salt$hash; NULL = no login yet
    created_at    TIMESTAMP DEFAULT now()
);

-- 3. delivery_partners — first-class, seeded; assignment logic is event-day
CREATE TABLE delivery_partners (
    partner_id        SERIAL PRIMARY KEY,
    name              TEXT NOT NULL,
    phone             TEXT,
    status            TEXT NOT NULL DEFAULT 'available',   -- available | busy | offline
    current_branch_id INT REFERENCES branches(branch_id),
    created_at        TIMESTAMP DEFAULT now()
);

-- 4. menu — brand-wide catalog (no stock here; stock is per-branch)
CREATE TABLE menu (
    id           SERIAL PRIMARY KEY,
    pizza_name   TEXT NOT NULL,
    price        NUMERIC(10,2) NOT NULL,
    diet_type    TEXT NOT NULL          -- veg | vegan | non-veg
);

-- 5. inventory — stock per pizza per branch (composite PK = junction table)
CREATE TABLE inventory (
    branch_id      INT NOT NULL REFERENCES branches(branch_id),
    menu_id        INT NOT NULL REFERENCES menu(id),
    stock_quantity INT NOT NULL,
    PRIMARY KEY (branch_id, menu_id)
);

-- 6. orders — the hub (branch + customer + nullable partner, money, status)
CREATE TABLE orders (
    order_id      SERIAL PRIMARY KEY,
    branch_id     INT NOT NULL REFERENCES branches(branch_id),
    customer_id   INT NOT NULL REFERENCES customers(customer_id),
    partner_id    INT REFERENCES delivery_partners(partner_id),   -- NULL = unclaimed (seam)
    order_time    TIMESTAMP DEFAULT now(),
    delivery_mode TEXT NOT NULL,          -- pickup | delivery
    subtotal      NUMERIC(10,2) NOT NULL,
    vat_percent   NUMERIC(5,2) NOT NULL,  -- 12.00 for Sweden
    vat_amount    NUMERIC(10,2) NOT NULL,
    total_price   NUMERIC(10,2) NOT NULL,
    status        TEXT NOT NULL DEFAULT 'order placed'  -- order placed|preparing|packed|delivered
);

-- 7. order_items — line items (one row per pizza type in an order)
CREATE TABLE order_items (
    item_id     SERIAL PRIMARY KEY,
    order_id    INT NOT NULL REFERENCES orders(order_id),
    menu_id     INT NOT NULL REFERENCES menu(id),
    quantity    INT NOT NULL,
    unit_price  NUMERIC(10,2) NOT NULL,   -- snapshot of menu.price at order time
    line_total  NUMERIC(10,2) NOT NULL
);
