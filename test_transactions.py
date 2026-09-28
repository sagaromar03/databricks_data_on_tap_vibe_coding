# Databricks notebook source
# /// script
# [tool.databricks.environment]
# environment_version = "5"
# ///
# MAGIC %md
# MAGIC # Data on Tap — Transactions Smoke Test
# MAGIC
# MAGIC Headless test of `backend/transactions.py` against the live Lakebase instance —
# MAGIC run this **before** wiring any UI. Set the widgets, then **Run All**.
# MAGIC
# MAGIC It exercises every function, including the headline **oversell / rollback** guard,
# MAGIC and asserts results. With `reset_db = yes` it re-runs `schema.sql` + `seed.sql`
# MAGIC first so every run starts from known stock (safe to re-run).

# COMMAND ----------

# MAGIC %pip install --upgrade 'databricks-sdk>=0.118.0'
# MAGIC dbutils.library.restartPython()

# COMMAND ----------

# MAGIC %md
# MAGIC ## Parameters

# COMMAND ----------

import os

dbutils.widgets.text("repo_root", "", "Repo root (blank = this notebook's folder)")
dbutils.widgets.text("branch_id", "1", "Branch id to test against")
dbutils.widgets.dropdown("reset_db", "yes", ["yes", "no"], "Reset DB (schema + seed) first?")

REPO_ROOT = dbutils.widgets.get("repo_root").strip() or os.getcwd()
BRANCH_ID = int(dbutils.widgets.get("branch_id"))
RESET_DB = dbutils.widgets.get("reset_db") == "yes"

print(f"repo_root : {REPO_ROOT}")
print(f"branch_id : {BRANCH_ID}")
print(f"reset_db  : {RESET_DB}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Import the backend
# MAGIC Add the repo root to the path so `from backend import transactions` resolves.

# COMMAND ----------

import sys

if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from backend import transactions as t
from backend.db import connection

print("Imported backend.transactions and backend.db")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Optional reset — known starting stock

# COMMAND ----------

if RESET_DB:
    for filename in ("schema.sql", "seed.sql"):
        with open(os.path.join(REPO_ROOT, filename)) as f:
            sql = f.read()
        with connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
            conn.commit()
        print(f"Ran {filename}")
else:
    print("Skipped reset (reset_db = no) — stock reflects whatever is currently in the DB")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Tiny assertion harness

# COMMAND ----------

_results = []


def check(name, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    _results.append((status, name))
    print(f"[{status}] {name}" + (f"  ({detail})" if detail else ""))


def stock_of(branch_id, menu_id):
    for row in t.get_menu(branch_id):
        if row["id"] == menu_id:
            return row["stock_quantity"]
    return None

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Reads

# COMMAND ----------

branches = t.get_branches()
customers = t.get_customers()
menu = t.get_menu(BRANCH_ID)

check("get_branches returns rows", len(branches) > 0, f"{len(branches)} branches")
check("get_customers returns rows", len(customers) > 0, f"{len(customers)} customers")
check("get_menu returns rows for branch", len(menu) > 0, f"{len(menu)} items")
check(
    "menu rows carry stock + price",
    all("stock_quantity" in m and "price" in m for m in menu),
)

customer_id = customers[0]["customer_id"]
print("\nMenu for branch", BRANCH_ID)
for m in menu:
    print(f"  id={m['id']:<3} {m['pizza_name']:16s} {m['price']:>6}  stock={m['stock_quantity']}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. place_order — happy path, VAT + stock decrement

# COMMAND ----------

from decimal import Decimal

item = next(m for m in menu if m["stock_quantity"] >= 2)  # pick a well-stocked pizza
before = stock_of(BRANCH_ID, item["id"])

result = t.place_order(
    BRANCH_ID, customer_id,
    [{"menu_id": item["id"], "quantity": 1}],
    "pickup",
)
after = stock_of(BRANCH_ID, item["id"])

expected_subtotal = item["price"] * 1
expected_vat = (expected_subtotal * Decimal("12.00") / Decimal("100")).quantize(Decimal("0.01"))

check("place_order returns an order_id", bool(result.get("order_id")))
check("subtotal correct", result["subtotal"] == expected_subtotal,
      f"{result['subtotal']} == {expected_subtotal}")
check("VAT is 12% of subtotal", result["vat_amount"] == expected_vat,
      f"{result['vat_amount']} == {expected_vat}")
check("total = subtotal + VAT",
      result["total_price"] == expected_subtotal + expected_vat)
check("stock decremented by 1", after == before - 1, f"{before} -> {after}")

happy_order_id = result["order_id"]
print("Order result:", result)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Oversell guard — the headline
# MAGIC Ordering more than is in stock must raise `OutOfStockError` and leave stock untouched (rollback).

# COMMAND ----------

scarce = min(t.get_menu(BRANCH_ID), key=lambda m: m["stock_quantity"])
stock_before = scarce["stock_quantity"]
too_many = stock_before + 1

raised = False
try:
    t.place_order(
        BRANCH_ID, customer_id,
        [{"menu_id": scarce["id"], "quantity": too_many}],
        "pickup",
    )
except t.OutOfStockError as e:
    raised = True
    print("Correctly raised OutOfStockError:", e)

stock_after = stock_of(BRANCH_ID, scarce["id"])
check("oversell raises OutOfStockError", raised,
      f"tried {too_many} of '{scarce['pizza_name']}' (stock {stock_before})")
check("stock unchanged after rollback", stock_after == stock_before,
      f"{stock_before} -> {stock_after}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Multi-item order rolls back fully if ONE line is short
# MAGIC A good line + a short line in the same order: the whole order must fail, and the good line's stock must be restored.

# COMMAND ----------

good = next(m for m in t.get_menu(BRANCH_ID) if m["stock_quantity"] >= 1)
short = min(t.get_menu(BRANCH_ID), key=lambda m: m["stock_quantity"])
good_before = stock_of(BRANCH_ID, good["id"])

raised = False
try:
    t.place_order(
        BRANCH_ID, customer_id,
        [
            {"menu_id": good["id"], "quantity": 1},
            {"menu_id": short["id"], "quantity": short["stock_quantity"] + 5},
        ],
        "delivery",
    )
except t.OutOfStockError:
    raised = True

good_after = stock_of(BRANCH_ID, good["id"])
check("mixed order raises OutOfStockError", raised)
check("good line's stock restored by rollback", good_after == good_before,
      f"{good_before} -> {good_after}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. get_orders — queue with line items

# COMMAND ----------

orders = t.get_orders(BRANCH_ID)
check("get_orders returns the placed order", any(o["order_id"] == happy_order_id for o in orders))
check("orders carry line items", all("items" in o for o in orders))
if orders:
    print("Most recent order:", orders[0]["order_id"], orders[0]["status"],
          "items:", [(i["pizza_name"], i["quantity"]) for i in orders[0]["items"]])

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. advance_status — lifecycle steps

# COMMAND ----------

s1 = t.advance_status(happy_order_id)
s2 = t.advance_status(happy_order_id)
s3 = t.advance_status(happy_order_id)
s4 = t.advance_status(happy_order_id)  # delivered
s5 = t.advance_status(happy_order_id)  # no-op, stays delivered

check("advances order placed -> preparing", s1 == "preparing", s1)
check("advances preparing -> packed", s2 == "packed", s2)
check("advances packed -> delivered", s3 == "delivered", s3)
check("delivered is a no-op", s4 == "delivered" and s5 == "delivered")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7. restock — relative add

# COMMAND ----------

target = t.get_menu(BRANCH_ID)[0]
before = stock_of(BRANCH_ID, target["id"])
new_qty = t.restock(BRANCH_ID, target["id"], 5)
check("restock returns new quantity", new_qty == before + 5, f"{before} + 5 -> {new_qty}")
check("restock is a relative add", stock_of(BRANCH_ID, target["id"]) == before + 5)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Summary

# COMMAND ----------

passed = sum(1 for s, _ in _results if s == "PASS")
failed = [name for s, name in _results if s == "FAIL"]
print(f"{passed}/{len(_results)} checks passed")
if failed:
    print("FAILED:")
    for name in failed:
        print("  -", name)
    raise AssertionError(f"{len(failed)} check(s) failed")
else:
    print("All checks passed.")