"""Business logic for Data on Tap.

Pure logic, zero UI. Streamlit imports and calls these directly; the React
frontend calls the same functions over HTTP via api.py. Money is returned as
Decimal (NUMERIC in the DB); round only on display.
"""

from decimal import Decimal

from .db import connection

VAT_PERCENT = Decimal("12.00")  # Sweden restaurant rate
DELIVERY_MODES = ("pickup", "delivery")

# Order status lifecycle (stored lowercase, matched exactly everywhere).
STATUS_FLOW = ["order placed", "preparing", "packed", "delivered"]


class OutOfStockError(Exception):
    """Raised when a requested quantity exceeds available stock; rolls the order back."""

    def __init__(self, branch_id, menu_id, requested):
        self.branch_id = branch_id
        self.menu_id = menu_id
        self.requested = requested
        super().__init__(
            f"Insufficient stock for menu {menu_id} at branch {branch_id} "
            f"(requested {requested})."
        )


def _rows_as_dicts(cur):
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def get_branches():
    """All branches, ordered by city then name (for the grouped dropdown)."""
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT branch_id, branch_name, city, address
            FROM branches
            ORDER BY city, branch_name
            """
        )
        return _rows_as_dicts(cur)


def get_customers():
    """All seeded customers (no real login in the MVP)."""
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT customer_id, name, email, phone FROM customers ORDER BY name"
        )
        return _rows_as_dicts(cur)


def get_menu(branch_id):
    """A branch's menu joined with its live stock, ordered by menu id."""
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT m.id, m.pizza_name, m.price, m.diet_type, i.stock_quantity
            FROM menu m
            JOIN inventory i ON i.menu_id = m.id
            WHERE i.branch_id = %s
            ORDER BY m.id
            """,
            (branch_id,),
        )
        return _rows_as_dicts(cur)


def place_order(branch_id, customer_id, items, delivery_mode):
    """Place an order as ONE atomic transaction (all-or-nothing).

    items: list of {"menu_id": int, "quantity": int}.

    Inserts the order and its line items, and decrements stock with a guarded
    UPDATE (`... AND stock_quantity >= qty`). If any line can't be satisfied,
    rows-affected is 0 -> OutOfStockError -> the whole transaction rolls back.
    Returns the order id and computed money fields.
    """
    if not items:
        raise ValueError("Cannot place an order with no items.")
    if delivery_mode not in DELIVERY_MODES:
        raise ValueError(
            f"delivery_mode must be one of {DELIVERY_MODES}, got {delivery_mode!r}."
        )
    for item in items:
        if item["quantity"] <= 0:
            raise ValueError(f"Quantity for menu {item['menu_id']} must be positive.")

    with connection() as conn:
        with conn:  # commits on success, rolls back on any exception
            with conn.cursor() as cur:
                menu_ids = [item["menu_id"] for item in items]
                cur.execute("SELECT id, price FROM menu WHERE id = ANY(%s)", (menu_ids,))
                price_by_id = {mid: price for mid, price in cur.fetchall()}
                missing = [m for m in menu_ids if m not in price_by_id]
                if missing:
                    raise ValueError(f"Unknown menu id(s): {missing}")

                subtotal = sum(
                    (price_by_id[item["menu_id"]] * item["quantity"] for item in items),
                    Decimal("0"),
                )
                vat_amount = (subtotal * VAT_PERCENT / Decimal("100")).quantize(Decimal("0.01"))
                total_price = subtotal + vat_amount

                cur.execute(
                    """
                    INSERT INTO orders (branch_id, customer_id, delivery_mode,
                                        subtotal, vat_percent, vat_amount, total_price)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING order_id
                    """,
                    (branch_id, customer_id, delivery_mode,
                     subtotal, VAT_PERCENT, vat_amount, total_price),
                )
                order_id = cur.fetchone()[0]

                for item in items:
                    menu_id = item["menu_id"]
                    qty = item["quantity"]
                    unit_price = price_by_id[menu_id]
                    line_total = unit_price * qty

                    cur.execute(
                        """
                        INSERT INTO order_items (order_id, menu_id, quantity, unit_price, line_total)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (order_id, menu_id, qty, unit_price, line_total),
                    )
                    # Atomic stock guard: serializes at the row, prevents overselling.
                    cur.execute(
                        """
                        UPDATE inventory
                        SET stock_quantity = stock_quantity - %s
                        WHERE branch_id = %s AND menu_id = %s AND stock_quantity >= %s
                        """,
                        (qty, branch_id, menu_id, qty),
                    )
                    if cur.rowcount == 0:
                        raise OutOfStockError(branch_id, menu_id, qty)

    return {
        "order_id": order_id,
        "subtotal": subtotal,
        "vat_percent": VAT_PERCENT,
        "vat_amount": vat_amount,
        "total_price": total_price,
    }


def get_orders(branch_id, include_delivered=False):
    """Order queue for a branch, newest first, each with its line items.

    By default hides delivered orders (the live kitchen queue).
    """
    status_filter = "" if include_delivered else "AND o.status <> 'delivered'"
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT o.order_id, o.order_time, o.status, o.delivery_mode,
                   o.subtotal, o.vat_amount, o.total_price, c.name AS customer_name
            FROM orders o
            JOIN customers c ON c.customer_id = o.customer_id
            WHERE o.branch_id = %s {status_filter}
            ORDER BY o.order_time DESC
            """,
            (branch_id,),
        )
        orders = _rows_as_dicts(cur)
        if not orders:
            return []

        order_ids = [o["order_id"] for o in orders]
        cur.execute(
            """
            SELECT oi.order_id, m.pizza_name, oi.quantity, oi.unit_price, oi.line_total
            FROM order_items oi
            JOIN menu m ON m.id = oi.menu_id
            WHERE oi.order_id = ANY(%s)
            ORDER BY oi.item_id
            """,
            (order_ids,),
        )
        items_by_order = {}
        for oid, name, qty, unit_price, line_total in cur.fetchall():
            items_by_order.setdefault(oid, []).append(
                {
                    "pizza_name": name,
                    "quantity": qty,
                    "unit_price": unit_price,
                    "line_total": line_total,
                }
            )
        for order in orders:
            order["items"] = items_by_order.get(order["order_id"], [])
        return orders


def get_customer_orders(customer_id, limit=10):
    """A single customer's own orders (all branches), newest first, with items."""
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT o.order_id, o.order_time, o.status, o.delivery_mode,
                   o.total_price, b.branch_name
            FROM orders o
            JOIN branches b ON b.branch_id = o.branch_id
            WHERE o.customer_id = %s
            ORDER BY o.order_time DESC
            LIMIT %s
            """,
            (customer_id, limit),
        )
        orders = _rows_as_dicts(cur)
        if not orders:
            return []

        order_ids = [o["order_id"] for o in orders]
        cur.execute(
            """
            SELECT oi.order_id, m.pizza_name, oi.quantity
            FROM order_items oi
            JOIN menu m ON m.id = oi.menu_id
            WHERE oi.order_id = ANY(%s)
            ORDER BY oi.item_id
            """,
            (order_ids,),
        )
        items_by_order = {}
        for oid, name, qty in cur.fetchall():
            items_by_order.setdefault(oid, []).append({"pizza_name": name, "quantity": qty})
        for order in orders:
            order["items"] = items_by_order.get(order["order_id"], [])
        return orders


def advance_status(order_id):
    """Move an order to the next status in the lifecycle. Returns the new status.

    A delivered order is a no-op (stays delivered).
    """
    with connection() as conn:
        with conn:
            with conn.cursor() as cur:
                cur.execute("SELECT status FROM orders WHERE order_id = %s", (order_id,))
                row = cur.fetchone()
                if row is None:
                    raise ValueError(f"Order {order_id} not found.")
                current = row[0]
                idx = STATUS_FLOW.index(current)  # unknown status raises ValueError
                if idx == len(STATUS_FLOW) - 1:
                    return current
                new_status = STATUS_FLOW[idx + 1]
                cur.execute(
                    "UPDATE orders SET status = %s WHERE order_id = %s",
                    (new_status, order_id),
                )
    return new_status


def restock(branch_id, menu_id, amount):
    """Add stock with a RELATIVE update (never an absolute set). Returns new quantity.

    A relative add is concurrency-safe: an absolute set would clobber a
    simultaneous order's decrement.
    """
    if amount <= 0:
        raise ValueError("Restock amount must be positive.")
    with connection() as conn:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE inventory
                    SET stock_quantity = stock_quantity + %s
                    WHERE branch_id = %s AND menu_id = %s
                    RETURNING stock_quantity
                    """,
                    (amount, branch_id, menu_id),
                )
                row = cur.fetchone()
                if row is None:
                    raise ValueError(
                        f"No inventory row for branch {branch_id}, menu {menu_id}."
                    )
                new_quantity = row[0]
    return new_quantity
