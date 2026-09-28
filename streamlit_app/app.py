"""Data on Tap — Streamlit UI.

Two pages, switched via the sidebar nav:
  - Order: customer signs in, then browses their branch's menu with live stock,
    builds a cart, sees subtotal/VAT/total, and places an order. Scoped to the
    logged-in customer — they only ever see their own account and orders.
  - Kitchen: live order queue (advance status) + per-branch stock and restock.

Imports backend modules directly and calls them in-process. No UI logic lives
in the backend; this file holds no SQL.
"""

import sys
from pathlib import Path
from decimal import Decimal

import streamlit as st

# Make the repo root importable so `from backend import ...` resolves when run
# as `streamlit run streamlit_app/app.py` from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import theme  # noqa: E402  (same-dir module; presentation layer)
from backend import transactions as t  # noqa: E402
from backend import auth  # noqa: E402

st.set_page_config(page_title="Data on Tap", page_icon="🍕", layout="wide")


@st.cache_data(ttl=300)
def load_branches():
    return t.get_branches()


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
def auth_gate():
    """Render login/signup until authenticated. Returns the customer dict or None."""
    if "auth_customer" in st.session_state:
        return st.session_state["auth_customer"]

    theme.hero(st, "Welcome", "Sign in to order")
    _, mid, _ = st.columns([1, 2, 1])
    with mid:
        login_tab, signup_tab = st.tabs(["Log in", "Sign up"])
        with login_tab:
            with st.form("login_form"):
                email = st.text_input("Email")
                password = st.text_input("Password", type="password")
                if st.form_submit_button("Log in", type="primary", use_container_width=True):
                    try:
                        st.session_state["auth_customer"] = auth.log_in(email, password)
                        st.rerun()
                    except auth.AuthError as e:
                        st.error(str(e))
            st.caption("Demo accounts use password `pizza` — e.g. `anna@example.se`.")
        with signup_tab:
            with st.form("signup_form"):
                name = st.text_input("Name")
                email = st.text_input("Email", key="su_email")
                password = st.text_input("Password (min 6 chars)", type="password", key="su_pw")
                if st.form_submit_button("Create account", type="primary", use_container_width=True):
                    try:
                        st.session_state["auth_customer"] = auth.sign_up(name, email, password)
                        st.rerun()
                    except auth.AuthError as e:
                        st.error(str(e))
    return None


def customer_view():
    customer = auth_gate()
    if customer is None:
        return

    theme.hero(st, "Order pizza", f"Signed in as {customer['name']}")

    if "last_order" in st.session_state:
        lo = st.session_state["last_order"]
        st.success(f"Order #{lo['id']} placed — total {lo['total']} kr. Enjoy!")

    left, right = st.columns([3, 2], gap="large")

    with left:
        bcol, ccol = st.columns(2)
        with bcol:
            branch = pick_branch("cust")
        branch_id = branch["branch_id"]
        with ccol:
            delivery_mode = st.radio(
                "Delivery mode", ["pickup", "delivery"], horizontal=True, key="cust_mode"
            )

        st.subheader("Menu")
        menu = t.get_menu(branch_id)
        cart = []
        for m in menu:
            with st.container(border=True):
                info, qcol = st.columns([5, 2])
                stock = int(m["stock_quantity"])
                info.markdown(
                    f"<span class='pizza-name'>{m['pizza_name']}</span> "
                    f"{theme.diet_badge(m['diet_type'])}"
                    f"<div class='item-sub'><span class='price'>{theme.money(m['price'])} kr</span> "
                    f"{theme.stock_pill(stock)}</div>",
                    unsafe_allow_html=True,
                )
                qty = qcol.number_input(
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
            lines = "".join(
                f"<div class='cart-line'><span><span class='q'>{it['quantity']} ×</span> "
                f"{it['name']}</span><span>{theme.money(it['price'] * it['quantity'])} kr</span></div>"
                for it in cart
            )
            st.markdown(lines, unsafe_allow_html=True)

        subtotal = sum((it["price"] * it["quantity"] for it in cart), Decimal("0"))
        vat = (subtotal * Decimal("12") / Decimal("100")).quantize(Decimal("0.01"))
        total = subtotal + vat

        st.markdown(
            f"<div class='summary'>"
            f"<div class='row'><span>Subtotal</span><span>{theme.money(subtotal)} kr</span></div>"
            f"<div class='row'><span>VAT (12%)</span><span>{theme.money(vat)} kr</span></div>"
            f"<div class='row total'><span>Total</span><span>{theme.money(total)} kr</span></div>"
            f"</div>",
            unsafe_allow_html=True,
        )
        st.write("")

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
                    "total": theme.money(result["total_price"]),
                }
                for it in cart:
                    st.session_state.pop(f"qty_{branch_id}_{it['menu_id']}", None)
                st.rerun()
            except t.OutOfStockError as e:
                st.error(f"{e} Someone grabbed the last one — adjust your cart.")

    my_orders = t.get_customer_orders(customer["customer_id"])
    if my_orders:
        st.subheader("Your recent orders")
        for o in my_orders:
            when = o["order_time"].strftime("%b %d · %H:%M") if hasattr(o["order_time"], "strftime") else str(o["order_time"])
            items = ", ".join(f"{i['quantity']}× {i['pizza_name']}" for i in o["items"])
            st.markdown(
                f"<div class='order-head'>Order #{o['order_id']} {theme.status_pill(o['status'])}</div>"
                f"<div class='order-meta'>{o['branch_name']} · {o['delivery_mode']} · {when}</div>"
                f"<div class='order-items'>{items}</div>"
                f"<span class='price'>{theme.money(o['total_price'])} kr</span>",
                unsafe_allow_html=True,
            )
            st.divider()


# --------------------------------------------------------------------------- #
# Kitchen view
# --------------------------------------------------------------------------- #
def kitchen_view():
    theme.hero(st, "Kitchen", "Live queue & stock")
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
                    when = ordered_at.strftime("%b %d · %H:%M") if hasattr(ordered_at, "strftime") else str(ordered_at)
                    lines = ", ".join(f"{i['quantity']}× {i['pizza_name']}" for i in o["items"])
                    st.markdown(
                        f"<div class='order-head'>Order #{o['order_id']} "
                        f"{theme.status_pill(o['status'])}</div>"
                        f"<div class='order-meta'>{o['customer_name']} · {o['delivery_mode']} · {when}</div>"
                        f"<div class='order-items'>{lines or '—'}</div>"
                        f"<span class='price'>{theme.money(o['total_price'])} kr</span>",
                        unsafe_allow_html=True,
                    )
                with action:
                    if o["status"] != "delivered":
                        if st.button("Advance ▶", key=f"adv_{o['order_id']}", use_container_width=True):
                            t.advance_status(o["order_id"])
                            st.rerun()

    with stock_tab:
        menu = t.get_menu(branch_id)
        for m in menu:
            with st.container(border=True):
                info, acol, bcol = st.columns([4, 2, 2])
                stock = int(m["stock_quantity"])
                info.markdown(
                    f"<span class='stock-name'>{m['pizza_name']}</span>"
                    f"<div class='item-sub'>{theme.stock_pill(stock)}</div>",
                    unsafe_allow_html=True,
                )
                amount = acol.number_input(
                    "add",
                    min_value=1,
                    value=5,
                    step=1,
                    key=f"restock_{branch_id}_{m['id']}",
                    label_visibility="collapsed",
                )
                if bcol.button("Restock", key=f"restock_btn_{branch_id}_{m['id']}", use_container_width=True):
                    t.restock(branch_id, m["id"], int(amount))
                    st.rerun()


# --------------------------------------------------------------------------- #
# Shell
# --------------------------------------------------------------------------- #
def main():
    theme.inject(st)
    with st.sidebar:
        st.title("🍕 Data on Tap")
        st.caption("Pizza ordering on Databricks Lakebase")
        if "auth_customer" in st.session_state:
            st.write(f"Signed in as **{st.session_state['auth_customer']['name']}**")
            if st.button("Log out", use_container_width=True):
                del st.session_state["auth_customer"]
                st.rerun()
        if st.button("Refresh data", use_container_width=True):
            load_branches.clear()
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
