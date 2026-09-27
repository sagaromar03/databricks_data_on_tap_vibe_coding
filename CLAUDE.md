# Data on Tap — Pizza Ordering App

## What this is
A transaction-first pizza ordering app built on Databricks, for a live "vibe coding"
event. It is a REAL ordering system backed by Lakebase (managed Postgres): place an
order, decrement stock atomically, run a kitchen queue. Analytics on a Delta medallion
is the documented next layer, not part of the MVP.

This repo is the **MVP spine**. On event day, features are built live ON TOP of it
(delivery-partner assignment, restock logging, analytics, geo). The spine's job is to
be solid, understood, and extensible — not feature-complete. A working simple app that
can be extended live beats an impressive one that can't be touched.

## Platform & environment
- Databricks Free Edition (AWS). No SSO/SCIM, no public app access, apps can't be made public.
- Lakebase instance: `data-on-tap` (managed Postgres). Connect with an OAuth token
  GENERATED IN CODE via databricks-sdk — never a static password. Host comes from the SDK.
- Working connection pattern (verified in a notebook):
  `w.database.get_database_instance(name="data-on-tap")` +
  `w.database.generate_database_credential(request_id=str(uuid.uuid4()),
  instance_names=["data-on-tap"])`, then
  `psycopg2.connect(host=instance.read_write_dns, dbname="databricks_postgres",
  user=<current_user>, password=<token>, sslmode="require")`.
  NOTE: the notebook that finally printed the menu used `w.postgres.*` after upgrading
  databricks-sdk>=0.118.0; if `w.postgres` is missing on a given SDK version, use
  `w.database.*` (the officially documented path). Keep BOTH in mind.
- Driver: the serverless runtime already ships psycopg2 (2.9.x) — import it, do NOT pip
  install extra copies. Stacking psycopg2 / psycopg2-binary / psycopg / psycopg-binary
  crashed the kernel on import. If a driver is genuinely missing, install exactly ONE and
  run `dbutils.library.restartPython()`.
- No Docker. Deploy = code + requirements.txt + app.yaml, pushed via Databricks CLI.

## Architecture (one platform, two planes)
    Streamlit App (Databricks App, SSO)  — read/write —>  Lakebase (Postgres)
                                                              |
                                                     [future] sync to Unity Catalog
                                                              v
                                                   Delta medallion -> analytics
- The app reads/writes Lakebase. Order placement is ONE atomic transaction.
- Hosting: Databricks App is the primary target, driven on a projector at the event.
  Audience interacts via a public Google Form (votes/suggestions), NOT the app itself
  (Free Edition apps can't be public).
- Local `streamlit run` is a zero-rework fallback — enabled by isolating ALL connection
  logic in `backend/db.py` (see Conventions).

## Repo structure (one backend, two frontends — monorepo)
    data-slice/
      backend/
        db.py            # ALL connection logic. get_connection() detects env
                         # (Databricks App injected creds vs local SDK token). Nothing
                         # else in the codebase calls psycopg2.connect().
        schema.sql       # DDL for all 7 tables
        seed.sql         # seed data (branches, menu, inventory, customers, partners)
        transactions.py  # place_order(), get_menu(), get_orders(), advance_status(),
                         # restock() — business logic. Imported and called directly.
        api.py           # thin REST layer wrapping transactions.py (React uses this;
                         # Streamlit does NOT need it)
      streamlit_app/
        app.py           # Streamlit UI. Imports backend/transactions.py directly.
      react_app/
        frontend/        # React UI (for the Tuesday comparison). Calls backend/api.py.
      CLAUDE.md
      requirements.txt   # streamlit, psycopg2-binary, databricks-sdk (+ fastapi, uvicorn for api.py)
      app.yaml           # Databricks App config (ignored by local streamlit run)

The core backend (db.py, schema.sql, transactions.py) is SHARED and identical for both
frontends. Streamlit calls transactions.py in-process. React calls the same functions
over HTTP via api.py. NEVER duplicate the backend per frontend.

## Data model (7 tables)
- branches:          branch_id PK, branch_name, city, address, latitude NULL, longitude NULL
- customers:         customer_id PK, name, email, phone, created_at
- delivery_partners: partner_id PK, name, phone, status DEFAULT 'available',
                     current_branch_id FK->branches, created_at
- menu:              id PK, pizza_name, price NUMERIC(10,2), diet_type ('veg'|'vegan'|'non-veg')
- inventory:         branch_id FK->branches, menu_id FK->menu, stock_quantity,
                     PRIMARY KEY (branch_id, menu_id)          # one stock row per pizza per branch
- orders:            order_id PK, branch_id FK, customer_id FK,
                     partner_id INT NULL FK->delivery_partners,
                     order_time DEFAULT now(), delivery_mode ('pickup'|'delivery'),
                     subtotal, vat_percent, vat_amount, total_price,
                     status DEFAULT 'order placed'
- order_items:       item_id PK, order_id FK, menu_id FK, quantity, unit_price, line_total

Relationships: branch/customer 1—* orders; order 1—* order_items; branch *—* menu via
inventory; branch *—* menu via order_items; partner 0/1 per order (nullable = unclaimed).
Two junction tables (inventory, order_items) do the relational work. `orders` is the hub.

## Core business logic — the atomic transaction (the heart of the app)
place_order(branch_id, customer_id, items[], delivery_mode) does ALL of this in ONE
transaction (all-or-nothing):
    BEGIN
      INSERT INTO orders (...) RETURNING order_id
      for each item:
        INSERT INTO order_items (order_id, menu_id, quantity, unit_price, line_total)
        UPDATE inventory SET stock_quantity = stock_quantity - :qty
          WHERE branch_id = :b AND menu_id = :m AND stock_quantity >= :qty
        if rows_affected == 0:  raise -> ROLLBACK   # sold out; reject whole order
      compute subtotal, vat_amount (12%), total_price; write onto the order
    COMMIT
The `WHERE stock_quantity >= :qty` + rows-affected check is the concurrency guard: it
serializes at the row and prevents overselling under simultaneous orders. This is the
correctness primitive AND the headline demo (two windows, 1 in stock, one wins).

Restock: UPDATE inventory SET stock_quantity = stock_quantity + :amount (RELATIVE add,
never absolute set — an absolute set clobbers a concurrent order's decrement).

## Key decisions (deliberate — state these confidently if asked)
- VAT: 12% (Sweden restaurant rate), stored per-order in vat_percent.
- Auth: none built. Databricks Apps enforces workspace SSO; app can't be public
  (Free Edition). In-app roles (customer / kitchen / branch) are a VIEW SELECTOR, not logins.
  Production answer: consumer tier runs outside Databricks; lakehouse holds data + governance.
- Customers & delivery_partners are first-class tables (seeded), even though the MVP has
  no real login — chosen over text-field stand-ins so event-day is pure logic.
- Branch selection: dropdown grouped by city. Multiple branches per city (city is an
  attribute, not identity). Geo/nearest-branch is a documented stretch (lat/long columns
  already present, nullable).
- delivery_mode stored ('pickup'|'delivery'); no partner logic in MVP.
- unit_price snapshotted into order_items (historical prices don't mutate).
- status lifecycle: 'order placed' -> 'preparing' -> 'packed' -> 'delivered'
  (stored lowercase exactly; add 'out for delivery' event-day when partners are live).
- Sync everywhere in MVP (correct at demo scale). Talking point: sync the core
  confirmation (stock/order), async the fan-out (email, kitchen notify, analytics).
- Scaling talking points (NOT built): connection pooling first, read replicas, queue-based
  load-leveling, hot-row sharding, partition by branch (branch_id is the natural shard key).

## Views (Streamlit)
- Customer: pick branch (grouped by city) -> browse that branch's menu with live stock
  ("N left") -> add items -> see subtotal / VAT / total -> pick delivery_mode -> place order
  -> confirmation. Quantity capped at available stock (UI guard; transaction is the truth).
- Kitchen: live order queue for a branch -> advance status; per-branch stock view + restock.

## Extension points (BUILD LIVE ON EVENT DAY — do not build in MVP)
- Delivery-partner assignment: broadcast + first-to-accept, resolved with the SAME atomic
  primitive: UPDATE orders SET partner_id=:me, status='assigned'
  WHERE order_id=:o AND partner_id IS NULL; rows-affected==1 wins. (partner_id already exists.)
- Concurrency demo harness: script N concurrent place_order() calls against 1-3 stock;
  project the result (exactly-in-stock succeed, rest rejected cleanly). No AI agents.
- Restock logging: add inventory_log (branch_id, menu_id, change_amount, reason, ts) for audit.
- Analytics: sync Lakebase -> Delta medallion (bronze/silver/gold); best sellers, revenue,
  VAT collected, orders by city and by branch, low-stock alerts. Genie NL queries.
- Geo: latitude/longitude on branches -> Haversine nearest-branch (more natural in React).
- Multi-item cart is already IN the MVP (order supports many order_items).

## Build order (backend-first, thin slices; test each piece before wiring UI)
1. schema.sql + seed.sql — create & seed all 7 tables; verify with SELECTs.
2. transactions.py — place_order (with atomic guard), get_menu, get_orders, advance_status,
   restock. Test EACH in a notebook cell BEFORE any UI.
3. streamlit_app/app.py — customer view, then kitchen view, wired to transactions.py.
4. Polish pass (theme + custom CSS on menu cards / order queue / stock pills) — LAST,
   as an isolated layer, using the frontend-design guidance. Presentation stays separate
   from logic (same discipline as db.py isolating the connection).
5. react_app + api.py — thin REST over transactions.py; React ordering screen for the
   Tuesday frontend comparison.

## Conventions
- ALL DB connection logic lives in backend/db.py behind get_connection(). Nothing else
  calls psycopg2.connect. This is what makes Databricks-App and local-streamlit interchangeable.
- Presentation isolated from logic: transactions.py has zero UI code; UI files call it.
- status values stored lowercase, matched exactly everywhere (a mismatch silently returns
  no rows — a classic 10-minutes-lost bug).
- Money as NUMERIC(10,2); round on display.
- Stock changes are RELATIVE (stock ± qty), never absolute sets — concurrency safety.
- Test backend pieces headless (notebook cell) before wiring to any UI.
- Do NOT re-add masking try/except during the build — let errors surface with full
  tracebacks; add graceful handling only for the demo.
