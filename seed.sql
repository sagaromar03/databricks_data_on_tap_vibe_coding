-- Data on Tap — seed data
-- Run after schema.sql. Idempotent-ish: assumes fresh tables (schema.sql drops/recreates).

-- Branches: 6 total, 2 per city (Stockholm, Goteborg, Malmo). lat/long left NULL for now.
INSERT INTO branches (branch_name, city, address) VALUES
    ('Pizza Hut Sodermalm',     'Stockholm', 'Gotgatan 12, Stockholm'),
    ('Pizza Hut Ostermalm',     'Stockholm', 'Sturegatan 4, Stockholm'),
    ('Pizza Hut Centrum',       'Goteborg',  'Kungsgatan 20, Goteborg'),
    ('Pizza Hut Majorna',       'Goteborg',  'Karl Johansgatan 40, Goteborg'),
    ('Pizza Hut Centrum',       'Malmo',     'Sodergatan 15, Malmo'),
    ('Pizza Hut Vastra Hamnen', 'Malmo',     'Isbergs gata 3, Malmo');

-- Menu: 6 pizzas, brand-wide catalog.
INSERT INTO menu (pizza_name, price, diet_type) VALUES
    ('Margherita',     9.00,  'veg'),
    ('Four Cheese',    11.00, 'veg'),
    ('Veggie Supreme', 11.50, 'veg'),
    ('Vegan Garden',   12.00, 'vegan'),
    ('Pepperoni',      11.00, 'non-veg'),
    ('BBQ Chicken',    12.50, 'non-veg');

-- Inventory: every (branch, pizza) pair. Varied stock so low-stock demo has triggers.
-- Cross join gives all 6x6=36 rows; base stock per pizza, then a couple deliberately low.
INSERT INTO inventory (branch_id, menu_id, stock_quantity)
SELECT b.branch_id, m.id,
       CASE m.pizza_name
           WHEN 'Margherita'     THEN 20
           WHEN 'Four Cheese'    THEN 14
           WHEN 'Veggie Supreme' THEN 12
           WHEN 'Vegan Garden'   THEN 6
           WHEN 'Pepperoni'      THEN 15
           WHEN 'BBQ Chicken'    THEN 4
       END
FROM branches b CROSS JOIN menu m;

-- Make one branch's popular items scarce for a clean concurrency/low-stock demo.
UPDATE inventory SET stock_quantity = 3
WHERE branch_id = 1 AND menu_id IN (SELECT id FROM menu WHERE pizza_name = 'Pepperoni');
UPDATE inventory SET stock_quantity = 2
WHERE branch_id = 1 AND menu_id IN (SELECT id FROM menu WHERE pizza_name = 'BBQ Chicken');

-- Customers: a handful of fake people to pick from.
INSERT INTO customers (name, email, phone) VALUES
    ('Anna Svensson',   'anna@example.se',   '070-1111111'),
    ('Erik Lindqvist',  'erik@example.se',   '070-2222222'),
    ('Sara Johansson',  'sara@example.se',   '070-3333333'),
    ('Johan Berg',      'johan@example.se',  '070-4444444'),
    ('Lena Nilsson',    'lena@example.se',   '070-5555555');

-- Delivery partners: a few, assigned to branches (event-day assignment logic uses these).
INSERT INTO delivery_partners (name, phone, status, current_branch_id) VALUES
    ('Oskar Falk',    '070-6666666', 'available', 1),
    ('Maja Holm',     '070-7777777', 'available', 1),
    ('Nils Ek',       '070-8888888', 'available', 3),
    ('Freja Lund',    '070-9999999', 'available', 5);
