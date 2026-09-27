"""Data on Tap — Streamlit UI.

Two separate pages (a view selector, not a login), switched via the sidebar nav:
  - Customer: pick branch -> browse menu with live stock -> build cart ->
    see subtotal/VAT/total -> pick delivery mode -> place order.
  - Kitchen: live order queue (advance status) + per-branch stock and restock.

Imports backend/transactions.py directly and calls it in-process. No UI logic
lives in the backend; this file holds no SQL.
"""

import sys
from pathlib import Path
from decimal import Decimal

import streamlit as st

# Make the repo root importable so `from backend import ...` resolves when run
# as `streamlit run streamlit_app/app.py` from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend import transactions as t  # noqa: E402

st.set_page_config(page_title="Data on Tap", page_icon="🍕", layout="wide")


def money(value):
    return f"{Decimal(value):.2f}"


@st.cache_data(ttl=300)
def load_branches():
    return t.get_branches()


@st.cache_data(ttl=300)
def load_customers():
    return t.get_customers()


def pick_branch(key_prefix):
    """City dropdown -> branch dropdown (multiple branches per city). Returns a branch dict."""
    branches = load_branches()
    cities = sorted({b["city"] for b in branches})
    city = st.selectbox("City", cities, key=f"{key_prefix}_city")
    city_branches = [b for b in branches if b["city"] == city]
    return st.selectbox(
        "Branch",
        city_branches,
        format_func=lambda b: b["branch_name"],
        key=f"{key_prefix}_branch",
    )


# --------------------------------------------------------------------------- #
# Customer view
# --------------------------------------------------------------------------- #
def customer_view():
    st.header("Order pizza")

    if "last_order" in st.session_state:
        lo = st.session_state["last_order"]
        st.success(f"Order #{lo['id']} placed — total {lo['total']} kr. Enjoy!")

    left, right = st.columns([3, 2])

    with left:
        branch = pick_branch("cust")
        branch_id = branch["branch_id"]

        customers = load_customers()
        customer = st.selectbox(
            "Ordering as",
            customers,
            format_func=lambda c: c["name"],
            key="cust_customer",
        )

        delivery_mode = st.radio(
            "Delivery mode", ["pickup", "delivery"], horizontal=True, key="cust_mode"
        )

        st.subheader("Menu")
        menu = t.get_menu(branch_id)
        cart = []
        for m in menu:
            c1, c2, c3, c4 = st.columns([4, 2, 2, 2])
            c1.markdown(f"**{m['pizza_name']}**  \n*{m['diet_type']}*")
            c2.write(f"{money(m['price'])} kr")
            stock = int(m["stock_quantity"])
            c3.write(f"{stock} left" if stock > 0 else "sold out")
            qty = c4.number_input(
                "qty",
                min_value=0,
                max_value=stock,
                step=1,
                key=f"qty_{branch_id}_{m['id']}",
                label_visibility="collapsed",
                disabled=stock == 0,
            )
            if qty > 0:
                cart.append(
                    {
                        "menu_id": m["id"],
                        "quantity": int(qty),
                        "price": m["price"],
                        "name": m["pizza_name"],
                    }
                )

    with right:
        st.subheader("Your order")
        if not cart:
            st.caption("Add pizzas from the menu to build your order.")
        else:
            for it in cart:
                st.write(f"{it['quantity']} × {it['name']} — {money(it['price'] * it['quantity'])} kr")

        subtotal = sum((it["price"] * it["quantity"] for it in cart), Decimal("0"))
        vat = (subtotal * Decimal("12") / Decimal("100")).quantize(Decimal("0.01"))
        total = subtotal + vat

        st.divider()
        st.write(f"Subtotal: **{money(subtotal)} kr**")
        st.write(f"VAT (12%): **{money(vat)} kr**")
        st.write(f"Total: **{money(total)} kr**")

        if st.button("Place order", type="primary", disabled=not cart, use_container_width=True):
            try:
                result = t.place_order(
                    branch_id,
                    customer["customer_id"],
                    [{"menu_id": it["menu_id"], "quantity": it["quantity"]} for it in cart],
                    delivery_mode,
                )
                st.session_state["last_order"] = {
                    "id": result["order_id"],
                    "total": money(result["total_price"]),
                }
                for it in cart:
                    st.session_state.pop(f"qty_{branch_id}_{it['menu_id']}", None)
                st.rerun()
            except t.OutOfStockError as e:
                st.error(f"{e} Someone grabbed the last one — adjust your cart.")


# --------------------------------------------------------------------------- #
# Kitchen view
# --------------------------------------------------------------------------- #
STATUS_LABELS = {
    "order placed": "🟡 order placed",
    "preparing": "🔵 preparing",
    "packed": "🟣 packed",
    "delivered": "🟢 delivered",
}


def kitchen_view():
    st.header("Kitchen")
    branch = pick_branch("kitchen")
    branch_id = branch["branch_id"]

    queue_tab, stock_tab = st.tabs(["Order queue", "Stock & restock"])

    with queue_tab:
        show_delivered = st.checkbox("Show delivered orders", value=False)
        orders = t.get_orders(branch_id, include_delivered=show_delivered)
        if not orders:
            st.info("No orders in the queue.")
        for o in orders:
            with st.container(border=True):
                head, action = st.columns([5, 1])
                with head:
                    ordered_at = o["order_time"]
                    when = ordered_at.strftime("%b %d %H:%M") if hasattr(ordered_at, "strftime") else str(ordered_at)
                    st.markdown(
                        f"**Order #{o['order_id']}** · {o['customer_name']} · "
                        f"{o['delivery_mode']} · {when}"
                    )
                    lines = ", ".join(f"{i['quantity']}× {i['pizza_name']}" for i in o["items"])
                    st.write(lines or "—")
                    st.write(
                        f"{STATUS_LABELS.get(o['status'], o['status'])}  ·  "
                        f"**{money(o['total_price'])} kr**"
                    )
                with action:
                    if o["status"] != "delivered":
                        if st.button("Advance ▶", key=f"adv_{o['order_id']}", use_container_width=True):
                            t.advance_status(o["order_id"])
                            st.rerun()

    with stock_tab:
        menu = t.get_menu(branch_id)
        for m in menu:
            c1, c2, c3, c4 = st.columns([4, 2, 2, 2])
            c1.markdown(f"**{m['pizza_name']}**")
            c2.write(f"{int(m['stock_quantity'])} in stock")
            amount = c3.number_input(
                "add",
                min_value=1,
                value=5,
                step=1,
                key=f"restock_{branch_id}_{m['id']}",
                label_visibility="collapsed",
            )
            if c4.button("Restock", key=f"restock_btn_{branch_id}_{m['id']}", use_container_width=True):
                t.restock(branch_id, m["id"], int(amount))
                st.rerun()


# --------------------------------------------------------------------------- #
# Shell
# --------------------------------------------------------------------------- #
def main():
    with st.sidebar:
        st.title("🍕 Data on Tap")
        st.caption("Pizza ordering on Databricks Lakebase")
        if st.button("Refresh data", use_container_width=True):
            load_branches.clear()
            load_customers.clear()
            st.rerun()
        st.divider()

    nav = st.navigation(
        [
            st.Page(customer_view, title="Order", icon="🍕", url_path="order", default=True),
            st.Page(kitchen_view, title="Kitchen", icon="🧑‍🍳", url_path="kitchen"),
        ]
    )
    nav.run()


main()
