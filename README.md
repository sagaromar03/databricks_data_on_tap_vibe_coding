# Data on Tap

A transaction-first pizza ordering app built on **Databricks Lakebase** (managed Postgres),
for a live "vibe coding" event. It's a real ordering system: place an order, decrement stock
atomically, run a kitchen queue, and assign deliveries — all backed by a Lakebase project.

## What it does
- **Customer**: sign up / log in, browse a branch's menu with live stock, build a cart, see
  subtotal / VAT (12%) / total, place a pickup or delivery order. Separate Account, Addresses,
  and Order-history pages, scoped to the signed-in customer.
- **Kitchen** (staff, branch-scoped): live order queue with status advance, plus stock + restock.
- **Delivery partner** (branch-scoped): accept / reject available deliveries and mark delivered.

The heart of the app is the **atomic transaction**: `place_order` inserts the order and its
items and decrements stock in one all-or-nothing operation, guarded by
`UPDATE inventory ... WHERE stock_quantity >= qty` — so two orders racing for the last pizza
can't oversell. The same first-to-accept primitive powers delivery assignment
(`UPDATE orders ... WHERE partner_id IS NULL`).

## Stack
- **Lakebase** project `data-on-tap` (autoscaling Postgres), connected via the `w.postgres`
  SDK API with an OAuth token generated in code — no static password.
- **Streamlit** app (deployable as a Databricks App, or `streamlit run` locally).
- Passwords hashed with PBKDF2 (Python stdlib). psycopg2 for Postgres.

## Layout
    backend/       db.py (all connection logic), schema.sql, seed.sql,
                   transactions.py (business logic), auth.py (login)
    streamlit_app/ app.py (UI), theme.py (CSS/helpers), assets/
    setup_database.py     notebook: connect -> schema -> seed -> grants -> verify
    test_transactions.py  notebook: headless backend tests
    app.yaml, requirements.txt, .streamlit/config.toml

## Setup
1. Create a Lakebase project named `data-on-tap` in your workspace.
2. Open `setup_database.py` as a Databricks notebook (from a Git folder), set `run_schema` and
   `run_seed` to **yes**, and **Run All** — it creates the 9 tables, seeds data, and verifies.
3. To deploy as a Databricks App, attach the Lakebase project as a resource and set the
   `app_client_id` widget in `setup_database.py` to the app's service-principal client id so it
   also GRANTs that role access (otherwise the app hits `permission denied`).

## Demo logins
- Customer: `anna@example.se` / `pizza`
- Kitchen: `kitchen.goteborg@dataontap.se` / `kitchen`
- Delivery partner: `oskar@dataontap.se` (branch 1) or `nils@dataontap.se` (branch 3) / `partner`

See `CLAUDE.md` for the full architecture, data model, decisions, and roadmap.
