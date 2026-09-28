# Data on Tap — Pizza Ordering App

## What this is
A transaction-first pizza ordering app built on Databricks, for a live "vibe coding"
event. It is a REAL ordering system backed by Lakebase (managed Postgres): place an
order, decrement stock atomically, run a kitchen queue, and assign deliveries. Analytics
on a Delta medallion is the documented next layer, not part of the app yet.

Started as an MVP spine; features have since been built ON TOP of it live (customer login,
staff + delivery-partner roles, delivery accept/reject, a branded landing page). The spine
stayed solid and extensible — a working simple app that can be extended beats an impressive
one that can't be touched.

## Platform & environment
- Databricks Free Edition (AWS). No SSO/SCIM, no public app access, apps can't be made public.
- Lakebase is a **project** named `data-on-tap` (the autoscaling model), resource name
  `projects/data-on-tap`. It is managed by the **`w.postgres`** SDK API — NOT the legacy
  `w.database` (database-instance) API.
  - GOTCHA (cost us real time): `w.database.get_database_instance(name="data-on-tap")`
    returns "instance not found" because a *project* isn't a *database instance*. Use
    `w.postgres.*`. `w.database.list_database_instances()` returns empty for a project.
- Working connection pattern (in `backend/db.py`): find the project's read-write endpoint
  via `w.postgres.list_endpoints(<branch or project>)`, read its host from
  `endpoint.status.hosts.host`, mint a token with
  `w.postgres.generate_database_credential(endpoint=endpoint.name)`, then
  `psycopg2.connect(host=<host>, dbname="databricks_postgres", user=<current_user>,
  password=<token>, sslmode="require")`. Token is generated IN CODE — never a static password.
- Driver: the serverless runtime already ships psycopg2 (2.9.x) — import it, do NOT pip
  install extra copies (stacking psycopg2 variants crashes the kernel on import).
- No Docker. Deploy = code + requirements.txt + app.yaml, pushed via Databricks CLI.
- **Grants**: a deployed Databricks App connects as its service principal (a Postgres role
  named the SP's client id = the app's `PGUSER`). Tables are owned by whoever ran the DDL,
  so the app's role needs `GRANT`s or it hits `permission denied for table ...`. Run the
  grant step in `setup_database.py` (`app_client_id` widget), or GRANT manually. Sequence
  grants are required too (SERIAL inserts call nextval).

## Architecture (one platform, two planes)
    Streamlit App (Databricks App, SSO)  — read/write —>  Lakebase project (Postgres)
                                                              |
                                                     [future] sync to Unity Catalog
                                                              v
                                                   Delta medallion -> analytics
- The app reads/writes Lakebase. Order placement and delivery assignment are atomic transactions.
- Hosting: Databricks App on a projector at the event. Audience interacts via a public Google
  Form (Free Edition apps can't be public).
- Local `streamlit run` is a zero-rework fallback — enabled by isolating ALL connection logic
  in `backend/db.py`.

## Repo structure (monorepo)
    data-on-tap/
      backend/
        db.py            # ALL connection logic behind get_connection(). Projects API
                         # (w.postgres) locally/notebook; injected PG* env vars in a
                         # Databricks App. Nothing else calls psycopg2.connect().
        schema.sql       # DDL for all 9 tables
        seed.sql         # seed data (branches, menu, inventory, customers, staff,
                         # delivery_partners, addresses) + demo password hashes
        transactions.py  # place_order, get_menu, get_orders, advance_status, restock,
                         # addresses CRUD, get_customer_orders, delivery accept/deliver
        auth.py          # customer signup/login, staff_log_in, partner_log_in (pbkdf2)
        api.py           # [not built yet] thin REST layer for the React frontend
      streamlit_app/
        app.py           # Streamlit UI: landing + role pages. Imports backend directly.
        theme.py         # presentation layer (CSS + render helpers), no logic/SQL
        assets/          # databricks-logo.svg (drop the official asset here)
      react_app/         # [not built yet] React UI for the frontend comparison
      setup_database.py  # notebook: connect, run schema+seed, grant app access, verify
      test_transactions.py # notebook: headless assertions over the backend
      .streamlit/config.toml  # theme (warm dark, tomato accent)
      requirements.txt   # streamlit, psycopg2-binary, databricks-sdk
      app.yaml           # Databricks App config (command: streamlit run streamlit_app/app.py)

The core backend (db.py, schema.sql, transactions.py, auth.py) is SHARED. Streamlit calls
transactions.py / auth.py in-process. NEVER duplicate the backend per frontend.

## Data model (9 tables)
- branches:          branch_id PK, branch_name, city, address, latitude NULL, longitude NULL
- customers:         customer_id PK, name, email NOT NULL UNIQUE, phone,
                     password_hash (pbkdf2, NULL = no login), created_at
- staff:             staff_id PK, name, email UNIQUE, password_hash, branch_id FK->branches
                     — kitchen/ops logins, org-provisioned (no self-signup), branch-scoped
- delivery_partners: partner_id PK, name, email UNIQUE NULL, password_hash NULL, phone,
                     status DEFAULT 'available', current_branch_id FK->branches, created_at
- customer_addresses: address_id PK, customer_id FK->customers, label, street, city, postal_code
- menu:              id PK, pizza_name, price NUMERIC(10,2), diet_type ('veg'|'vegan'|'non-veg')
- inventory:         branch_id FK, menu_id FK, stock_quantity, PRIMARY KEY (branch_id, menu_id)
- orders:            order_id PK, branch_id FK, customer_id FK, partner_id INT NULL FK,
                     order_time, delivery_mode ('pickup'|'delivery'),
                     subtotal, vat_percent, vat_amount, total_price, status DEFAULT 'order placed'
- order_items:       item_id PK, order_id FK, menu_id FK, quantity, unit_price, line_total

Relationships: branch/customer 1—* orders; order 1—* order_items; customer 1—* addresses;
branch *—* menu via inventory and via order_items; partner 0/1 per order (NULL = unclaimed —
this is the delivery-assignment seam). `orders` is the hub.

## Core business logic — the atomic transactions (the heart of the app)
place_order(branch_id, customer_id, items[], delivery_mode) — ONE all-or-nothing transaction:
    BEGIN
      look up prices; compute subtotal, vat_amount (12%), total_price
      INSERT INTO orders (...) RETURNING order_id
      for each item:
        INSERT INTO order_items (...)
        UPDATE inventory SET stock_quantity = stock_quantity - :qty
          WHERE branch_id=:b AND menu_id=:m AND stock_quantity >= :qty
        if rows_affected == 0:  raise OutOfStockError -> ROLLBACK   # sold out; reject whole order
    COMMIT
The `WHERE stock_quantity >= :qty` + rows-affected check is the concurrency guard: it
serializes at the row and prevents overselling. Correctness primitive AND headline demo
(two windows, 1 in stock, one wins).

claim_delivery(order_id, partner_id) — the SAME primitive, reused for delivery assignment:
    UPDATE orders SET partner_id=:me, status='out for delivery'
      WHERE order_id=:o AND partner_id IS NULL
    rows_affected == 1 wins; 0 -> DeliveryClaimError (another partner got it first).

restock: UPDATE inventory SET stock_quantity = stock_quantity + :amount (RELATIVE add,
never absolute set — an absolute set clobbers a concurrent order's decrement).

## Auth & roles (BUILT)
- **Customers** self-sign up and log in. Passwords hashed with PBKDF2-HMAC-SHA256 (stdlib,
  no extra dependency), stored as `pbkdf2_sha256$iter$salt$hash`; never plaintext. Login uses
  a uniform "invalid email or password" so it can't reveal which emails exist.
- **Kitchen (staff)** and **Delivery partner** accounts are org-provisioned — no self-signup,
  each tied to a branch. They log in on their own tab of the landing page.
- Role-based navigation: a customer sees Menu + their account pages (never Kitchen); staff see
  only their branch's Kitchen; partners see only their branch's Deliveries.
- **Data is scoped by role**: customer views use the logged-in `customer_id`; address
  edit/delete and order reads are guarded by `customer_id`; deliveries by branch/partner. This
  is the RBAC — a customer can't see or touch another customer's data even by guessing an id.
- Session note: Streamlit `session_state` resets on a full browser refresh (logs the user out).
  Fine for the demo; production login would persist via cookies.
- Demo logins: customer `anna@example.se`/`pizza`; kitchen `kitchen.goteborg@dataontap.se`/
  `kitchen`; partner `oskar@dataontap.se` (branch 1) or `nils@dataontap.se` (branch 3)/`partner`.

## Key decisions (deliberate — state these confidently if asked)
- VAT: 12% (Sweden restaurant rate), stored per-order in vat_percent.
- Production auth answer: the consumer tier runs OUTSIDE Databricks (real web app + IdP);
  the lakehouse holds data + governance. The in-app login here is a demo of the full flow.
- Branch selection: dropdown grouped by city. Multiple branches per city (city is an attribute,
  not identity). Geo/nearest-branch is a stretch (lat/long columns present, nullable).
- unit_price snapshotted into order_items (historical prices don't mutate).
- status lifecycle: pickup = 'order placed' -> 'preparing' -> 'packed' -> 'delivered';
  delivery adds 'out for delivery' (partner accepts a packed order, then marks delivered).
  Stored lowercase, matched exactly. Kitchen queue hides 'out for delivery' and 'delivered'.
- Sync everywhere (correct at demo scale). Talking point: sync the core confirmation
  (stock/order), async the fan-out (email, kitchen notify, analytics).
- Scaling talking points (NOT built): connection pooling first, read replicas, queue-based
  load-leveling, hot-row sharding, partition by branch (branch_id is the natural shard key).

## Views (Streamlit)
- **Landing**: split-screen — branded animated panel (one-shot pizza-slice entrance,
  "Powered by Databricks") + a "Sign in as" role picker (Customer / Kitchen / Delivery partner).
- **Customer**: Menu (branch grouped by city -> live stock "N left" -> cart -> subtotal/VAT/
  total -> pickup/delivery -> place order), plus separate pages: Account, Addresses (list +
  add/edit/delete), Order history.
- **Kitchen** (staff, branch-scoped): order queue -> advance status; stock + relative restock.
- **Delivery partner** (branch-scoped): Available deliveries (Accept / Reject) and Out for
  delivery (Mark delivered). Accept is the atomic first-to-accept claim.

## Extension points / roadmap
BUILT since the MVP: customer login, staff + delivery-partner roles, delivery accept/reject
(the first-to-accept primitive), Account/Addresses/Order-history pages, branded landing.
Still open:
- Concurrency demo harness: script N concurrent place_order() (or claim_delivery) calls
  against 1–3 stock / one delivery; project the clean win/reject. No AI agents.
- Restock logging: inventory_log (branch, menu, change_amount, reason, ts) for audit.
- Analytics: sync Lakebase -> Delta medallion (bronze/silver/gold); best sellers, revenue,
  VAT collected, orders by city/branch, low-stock alerts. Genie NL queries.
- Geo: latitude/longitude -> Haversine nearest-branch (more natural in React).
- React frontend + backend/api.py (thin REST). Could use the Lakebase **Data API**
  (PostgREST) for simple reads — but transactional writes stay on direct Postgres.

## Conventions
- ALL DB connection logic lives in backend/db.py behind get_connection(). Nothing else calls
  psycopg2.connect. This is what makes Databricks-App and local-streamlit interchangeable.
- Presentation isolated from logic: transactions.py / auth.py have zero UI code; theme.py holds
  the CSS/render helpers; UI files call the backend.
- Passwords hashed with PBKDF2 (stdlib); never store or log plaintext. Uniform login errors.
- RBAC by ownership: scope reads/writes with customer_id / partner_id / branch_id guards.
- status values stored lowercase, matched exactly (a mismatch silently returns no rows).
- Money as NUMERIC(10,2), Decimal in Python; round on display.
- Stock changes are RELATIVE (stock ± qty), never absolute sets — concurrency safety.
- Test backend pieces headless (setup_database.py / test_transactions.py) before wiring UI.
- Do NOT re-add masking try/except during the build — let errors surface with full tracebacks;
  add graceful handling only at real boundaries (auth, the two-API connection fallback, demo).
