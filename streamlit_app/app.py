"""Data on Tap — Streamlit UI.

Two pages, switched via the sidebar nav:
  - Order: customer signs in, then browses their branch's menu with live stock,
    builds a cart, sees subtotal/VAT/total, and places an order. Scoped to the
    logged-in customer — they only ever see their own account and orders.
  - Kitchen: live order queue (advance status) + per-branch stock and restock.

Imports backend modules directly and calls them in-process. No UI logic lives
in the backend; this file holds no SQL.
"""

import base64
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

# Page registry, populated in main(); lets views switch pages programmatically.
PAGES = {}


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
def _customer_forms():
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
        st.caption("Demo: `anna@example.se` / `pizza`.")
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


def _staff_form():
    with st.form("staff_login_form"):
        email = st.text_input("Staff email", key="st_email")
        password = st.text_input("Password", type="password", key="st_pw")
        if st.form_submit_button("Log in to kitchen", type="primary", use_container_width=True):
            try:
                st.session_state["auth_staff"] = auth.staff_log_in(email, password)
                st.rerun()
            except auth.AuthError as e:
                st.error(str(e))
    st.caption("Kitchen accounts are created by your organization. Demo: `kitchen.goteborg@dataontap.se` / `kitchen`.")


def _partner_form():
    with st.form("partner_login_form"):
        email = st.text_input("Partner email", key="pt_email")
        password = st.text_input("Password", type="password", key="pt_pw")
        if st.form_submit_button("Log in as partner", type="primary", use_container_width=True):
            try:
                st.session_state["auth_partner"] = auth.partner_log_in(email, password)
                st.rerun()
            except auth.AuthError as e:
                st.error(str(e))
    st.caption("Delivery-partner accounts are created by your organization. Demo: `oskar@dataontap.se` / `partner`.")


ROLE_ICONS = {"Customer": "🧑", "Kitchen": "🧑‍🍳", "Delivery partner": "🛵"}


# Placeholder mark used only until the official Databricks logo asset is added.
DATABRICKS_MARK = (
    "<svg width='16' height='16' viewBox='0 0 32 32' xmlns='http://www.w3.org/2000/svg'>"
    "<path d='M2 9 L16 3 L30 9 L16 15 Z' fill='#fff' opacity='1'/>"
    "<path d='M2 16 L16 10 L30 16 L16 22 Z' fill='#fff' opacity='.72'/>"
    "<path d='M2 23 L16 17 L30 23 L16 29 Z' fill='#fff' opacity='.48'/>"
    "</svg>"
)

_ASSETS = Path(__file__).resolve().parent / "assets"


def _databricks_logo_html():
    """Render the official Databricks logo if the asset file is present.

    Drop the real logo at streamlit_app/assets/databricks-logo.svg (or .png) —
    download it from Databricks' brand/press page; do not recreate it. Until
    then this falls back to a neutral placeholder mark + wordmark.
    """
    for name, mime in (("databricks-logo.svg", "image/svg+xml"),
                        ("databricks-logo.png", "image/png")):
        f = _ASSETS / name
        if f.exists():
            data = base64.b64encode(f.read_bytes()).decode()
            return (
                f"<img src='data:{mime};base64,{data}' alt='Databricks' "
                "style='height:22px;vertical-align:middle;'/>"
            )
    return f"{DATABRICKS_MARK} <b>Databricks</b>"


def login_page():
    """Split landing — branded left panel, sign-in on the right."""
    # Play the slice's entrance animation only on the first render this session.
    first_load = not st.session_state.get("banner_shown", False)
    st.session_state["banner_shown"] = True
    panel_class = "split-left animate-in" if first_load else "split-left"

    left, right = st.columns(2, gap="large")
    with left:
        st.markdown(
            f"<div class='{panel_class}'>"
            f"<div class='banner-pizza'>{theme.PIZZA}</div>"
            "<div>"
            "<div class='eyebrow'>Pizza ordering on Lakebase</div>"
            "<h1>Data on Tap</h1>"
            "<p>Order from your nearest branch, watch the kitchen work the queue, "
            "and get it delivered — one atomic transaction at a time.</p>"
            "</div>"
            f"<div class='poweredby'>Powered by {_databricks_logo_html()}</div>"
            "</div>",
            unsafe_allow_html=True,
        )
    with right:
        st.markdown("<div class='right-head'>🍕 Data on Tap</div>", unsafe_allow_html=True)
        role = st.selectbox(
            "Sign in as", ["Customer", "Kitchen", "Delivery partner"], key="login_role"
        )
        if role == "Customer":
            _customer_forms()
        elif role == "Kitchen":
            _staff_form()
        else:
            _partner_form()


def menu_view():
    customer = st.session_state.get("auth_customer")
    if customer is None:
        st.info("Please sign in to order.")
        return

    theme.hero(st, "Menu", f"Signed in as {customer['name']}")

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
                    "<div class='menu-row'>"
                    f"{theme.pizza_svg(36)}"
                    "<div>"
                    f"<span class='pizza-name'>{m['pizza_name']}</span> "
                    f"{theme.diet_badge(m['diet_type'])}"
                    f"<div class='item-sub'><span class='price'>{theme.money(m['price'])} kr</span> "
                    f"{theme.stock_pill(stock)}</div>"
                    "</div></div>",
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


# --------------------------------------------------------------------------- #
# Account pages (each its own page)
# --------------------------------------------------------------------------- #
def _require_customer():
    customer = st.session_state.get("auth_customer")
    if customer is None:
        st.info("Please sign in first.")
    return customer


def account_view():
    customer = _require_customer()
    if customer is None:
        return
    theme.hero(st, "Account", "Your personal information")
    st.markdown(
        f"<div class='summary'>"
        f"<div class='row'><span>Customer ID</span><span>#{customer['customer_id']}</span></div>"
        f"<div class='row'><span>Name</span><span>{customer['name']}</span></div>"
        f"<div class='row'><span>Email</span><span>{customer['email']}</span></div>"
        f"</div>",
        unsafe_allow_html=True,
    )


def addresses_view():
    customer = _require_customer()
    if customer is None:
        return
    # Landing on the list clears any half-finished edit.
    st.session_state.pop("edit_address_id", None)

    theme.hero(st, "Addresses", "Your saved delivery addresses")

    if st.button("＋ Add address", type="primary"):
        st.switch_page(PAGES["address_form"])

    addresses = t.get_addresses(customer["customer_id"])
    if not addresses:
        st.caption("No saved addresses yet.")
    for a in addresses:
        with st.container(border=True):
            info, edit_c, del_c = st.columns([6, 1, 1])
            info.markdown(
                f"<div class='order-head'>{a['label'] or 'Address'}</div>"
                f"<div class='order-meta'>{a['street']}, {a.get('postal_code') or ''} {a['city']}</div>",
                unsafe_allow_html=True,
            )
            if edit_c.button("Edit", key=f"edit_{a['address_id']}", use_container_width=True):
                st.session_state["edit_address_id"] = a["address_id"]
                st.switch_page(PAGES["address_form"])
            if del_c.button("Delete", key=f"del_{a['address_id']}", use_container_width=True):
                t.delete_address(a["address_id"], customer["customer_id"])
                st.rerun()


def address_form_view():
    customer = _require_customer()
    if customer is None:
        return

    edit_id = st.session_state.get("edit_address_id")
    existing = t.get_address(edit_id, customer["customer_id"]) if edit_id else None
    title = "Edit address" if existing else "Add address"
    theme.hero(st, title, "")

    with st.form("address_form"):
        label = st.text_input("Label", value=(existing["label"] if existing else "Home"))
        street = st.text_input("Street", value=(existing["street"] if existing else ""))
        city = st.text_input("City", value=(existing["city"] if existing else ""))
        postal = st.text_input("Postal code", value=(existing.get("postal_code") if existing else "") or "")
        save, cancel = st.columns(2)
        submitted = save.form_submit_button("Save", type="primary", use_container_width=True)
        cancelled = cancel.form_submit_button("Cancel", use_container_width=True)

    if cancelled:
        st.session_state.pop("edit_address_id", None)
        st.switch_page(PAGES["addresses"])
    if submitted:
        try:
            if existing:
                t.update_address(existing["address_id"], customer["customer_id"], label, street, city, postal)
            else:
                t.add_address(customer["customer_id"], label, street, city, postal)
            st.session_state.pop("edit_address_id", None)
            st.switch_page(PAGES["addresses"])
        except ValueError as e:
            st.error(str(e))


def order_history_view():
    customer = _require_customer()
    if customer is None:
        return
    theme.hero(st, "Order history", "Your past orders")
    my_orders = t.get_customer_orders(customer["customer_id"])
    if not my_orders:
        st.caption("No orders yet.")
    for o in my_orders:
        when = o["order_time"].strftime("%b %d · %H:%M") if hasattr(o["order_time"], "strftime") else str(o["order_time"])
        items = ", ".join(f"{i['quantity']}× {i['pizza_name']}" for i in o["items"])
        with st.container(border=True):
            st.markdown(
                f"<div class='order-head'>Order #{o['order_id']} {theme.status_pill(o['status'])}</div>"
                f"<div class='order-meta'>{o['branch_name']} · {o['delivery_mode']} · {when}</div>"
                f"<div class='order-items'>{items}</div>"
                f"<span class='price'>{theme.money(o['total_price'])} kr</span>",
                unsafe_allow_html=True,
            )


# --------------------------------------------------------------------------- #
# Kitchen view
# --------------------------------------------------------------------------- #
def kitchen_view():
    staff = st.session_state.get("auth_staff")
    if staff is None:
        st.info("Please sign in as staff to view the kitchen.")
        return
    theme.hero(st, "Kitchen", f"{staff['branch_name']} · {staff['name']}")
    branch_id = staff["branch_id"]

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
# Delivery-partner view
# --------------------------------------------------------------------------- #
def partner_view():
    partner = st.session_state.get("auth_partner")
    if partner is None:
        st.info("Please sign in as a delivery partner.")
        return
    branch_label = partner.get("branch_name") or "Unassigned"
    theme.hero(st, "Deliveries", f"{branch_label} · {partner['name']}")

    if not partner.get("branch_id"):
        st.info("You aren't assigned to a branch yet — ask your branch to add you.")
        return

    partner_id = partner["partner_id"]
    branch_id = partner["branch_id"]
    passed = st.session_state.setdefault("passed_orders", set())

    def _card(o):
        when = o["order_time"].strftime("%b %d · %H:%M") if hasattr(o["order_time"], "strftime") else str(o["order_time"])
        st.markdown(
            f"<div class='order-head'>Order #{o['order_id']} {theme.status_pill(o['status'])}</div>"
            f"<div class='order-meta'>{o['customer_name']} · {when}</div>"
            f"<span class='price'>{theme.money(o['total_price'])} kr</span>",
            unsafe_allow_html=True,
        )

    # Deliveries this partner has accepted.
    mine = t.get_my_deliveries(partner_id)
    st.subheader("Out for delivery")
    if not mine:
        st.caption("Nothing out for delivery right now.")
    for o in mine:
        with st.container(border=True):
            _card(o)
            if st.button("Mark delivered", key=f"deliver_{o['order_id']}", type="primary"):
                t.mark_delivered(o["order_id"], partner_id)
                st.rerun()

    # Unclaimed deliveries available to accept (minus ones this partner passed on).
    available = [o for o in t.get_delivery_orders(branch_id) if o["order_id"] not in passed]
    st.subheader(f"Available deliveries — {len(available)}")
    if not available:
        with st.container(border=True):
            st.markdown(
                "<div class='order-head'>All caught up 🎉</div>"
                f"<div class='order-meta'>No deliveries to accept at {branch_label} right now.</div>",
                unsafe_allow_html=True,
            )
    for o in available:
        with st.container(border=True):
            _card(o)
            accept_c, reject_c = st.columns(2)
            if accept_c.button("Accept", key=f"accept_{o['order_id']}", type="primary", use_container_width=True):
                try:
                    t.claim_delivery(o["order_id"], partner_id)
                    st.rerun()
                except t.DeliveryClaimError as e:
                    st.warning(str(e))
                    st.rerun()
            if reject_c.button("Reject", key=f"reject_{o['order_id']}", use_container_width=True):
                passed.add(o["order_id"])
                st.rerun()


# --------------------------------------------------------------------------- #
# Shell
# --------------------------------------------------------------------------- #
def main():
    theme.inject(st)
    signed_in = (
        st.session_state.get("auth_customer")
        or st.session_state.get("auth_staff")
        or st.session_state.get("auth_partner")
    )

    # Sidebar only once signed in; the landing page is clean and full-width.
    if signed_in:
        with st.sidebar:
            st.title("🍕 Data on Tap")
            st.caption("Pizza ordering on Databricks Lakebase")
            role = (
                "Kitchen" if "auth_staff" in st.session_state
                else "Delivery partner" if "auth_partner" in st.session_state
                else "Customer"
            )
            st.write(f"Signed in as **{signed_in['name']}** · {role}")
            if st.button("Log out", use_container_width=True):
                st.session_state.pop("auth_customer", None)
                st.session_state.pop("auth_staff", None)
                st.session_state.pop("auth_partner", None)
                st.rerun()
            if st.button("Refresh data", use_container_width=True):
                load_branches.clear()
                st.rerun()
            st.divider()

    if "auth_customer" in st.session_state:
        PAGES["menu"] = st.Page(menu_view, title="Menu", icon="🍕", url_path="menu", default=True)
        PAGES["account"] = st.Page(account_view, title="Account", icon="👤", url_path="account")
        PAGES["addresses"] = st.Page(addresses_view, title="Addresses", icon="📍", url_path="addresses")
        PAGES["address_form"] = st.Page(address_form_view, title="Add / edit address", icon="✏️", url_path="address-form")
        PAGES["orders"] = st.Page(order_history_view, title="Order history", icon="🧾", url_path="orders")
        pages = {
            "Shop": [PAGES["menu"]],
            "Your account": [PAGES["account"], PAGES["addresses"], PAGES["address_form"], PAGES["orders"]],
        }
        st.navigation(pages).run()
    elif "auth_staff" in st.session_state:
        st.navigation([st.Page(kitchen_view, title="Kitchen", icon="🧑‍🍳", url_path="kitchen", default=True)]).run()
    elif "auth_partner" in st.session_state:
        st.navigation([st.Page(partner_view, title="Deliveries", icon="🛵", url_path="deliveries", default=True)]).run()
    else:
        # Signed out: hide the nav chrome so the landing is a clean full-width page.
        st.navigation(
            [st.Page(login_page, title="Sign in", url_path="signin", default=True)],
            position="hidden",
        ).run()


main()
