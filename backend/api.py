"""Thin REST layer over the shared backend, for the React frontend.

FastAPI wraps transactions.py / auth.py — it holds NO business logic itself. The
same atomic transactions, RBAC, and password hashing live in the shared backend;
this file just exposes them over HTTP and guards each route by role via a JWT.

Run:  uvicorn backend.api:app --reload   (from the repo root)
"""

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import auth
from . import transactions as t

app = FastAPI(title="Data on Tap API")

# JWT signing secret. Set API_SECRET in the deployed app; this default is dev-only.
SECRET = os.environ.get("API_SECRET", "dev-secret-change-me")
TOKEN_HOURS = 12


# --------------------------------------------------------------------------- #
# Auth: issue and verify JWTs; role guards
# --------------------------------------------------------------------------- #
def _issue_token(role, identity):
    payload = {
        "role": role,
        **identity,
        "exp": datetime.now(timezone.utc) + timedelta(hours=TOKEN_HOURS),
    }
    return jwt.encode(payload, SECRET, algorithm="HS256")


def current_identity(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing bearer token")
    token = authorization.split(" ", 1)[1]
    try:
        return jwt.decode(token, SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(401, "Invalid or expired token")


def require(role):
    def dep(identity=Depends(current_identity)):
        if identity.get("role") != role:
            raise HTTPException(403, f"This route requires the {role} role.")
        return identity
    return dep


# --------------------------------------------------------------------------- #
# Request bodies
# --------------------------------------------------------------------------- #
class SignUp(BaseModel):
    name: str
    email: str
    password: str


class Login(BaseModel):
    email: str
    password: str


class OrderItem(BaseModel):
    menu_id: int
    quantity: int


class PlaceOrder(BaseModel):
    branch_id: int
    items: list[OrderItem]
    delivery_mode: str


class AddressBody(BaseModel):
    label: str = "Home"
    street: str
    city: str
    postal_code: str = ""


class RestockBody(BaseModel):
    menu_id: int
    amount: int


# --------------------------------------------------------------------------- #
# Public reads
# --------------------------------------------------------------------------- #
@app.get("/api/branches")
def branches():
    return t.get_branches()


@app.get("/api/menu")
def menu(branch_id: int):
    return t.get_menu(branch_id)


# --------------------------------------------------------------------------- #
# Auth routes
# --------------------------------------------------------------------------- #
@app.post("/api/auth/signup")
def signup(body: SignUp):
    try:
        customer = auth.sign_up(body.name, body.email, body.password)
    except auth.AuthError as e:
        raise HTTPException(400, str(e))
    return {"token": _issue_token("customer", customer), "customer": customer}


@app.post("/api/auth/login")
def login(body: Login):
    try:
        customer = auth.log_in(body.email, body.password)
    except auth.AuthError as e:
        raise HTTPException(401, str(e))
    return {"token": _issue_token("customer", customer), "customer": customer}


@app.post("/api/auth/staff/login")
def staff_login(body: Login):
    try:
        staff = auth.staff_log_in(body.email, body.password)
    except auth.AuthError as e:
        raise HTTPException(401, str(e))
    return {"token": _issue_token("staff", staff), "staff": staff}


@app.post("/api/auth/partner/login")
def partner_login(body: Login):
    try:
        partner = auth.partner_log_in(body.email, body.password)
    except auth.AuthError as e:
        raise HTTPException(401, str(e))
    return {"token": _issue_token("partner", partner), "partner": partner}


# --------------------------------------------------------------------------- #
# Customer routes
# --------------------------------------------------------------------------- #
@app.post("/api/orders")
def place_order(body: PlaceOrder, me=Depends(require("customer"))):
    items = [{"menu_id": i.menu_id, "quantity": i.quantity} for i in body.items]
    try:
        return t.place_order(body.branch_id, me["customer_id"], items, body.delivery_mode)
    except t.OutOfStockError as e:
        raise HTTPException(409, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/api/orders/mine")
def my_orders(me=Depends(require("customer"))):
    return t.get_customer_orders(me["customer_id"])


@app.get("/api/addresses")
def list_addresses(me=Depends(require("customer"))):
    return t.get_addresses(me["customer_id"])


@app.post("/api/addresses")
def add_address(body: AddressBody, me=Depends(require("customer"))):
    try:
        address_id = t.add_address(me["customer_id"], body.label, body.street, body.city, body.postal_code)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"address_id": address_id}


@app.put("/api/addresses/{address_id}")
def update_address(address_id: int, body: AddressBody, me=Depends(require("customer"))):
    try:
        t.update_address(address_id, me["customer_id"], body.label, body.street, body.city, body.postal_code)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True}


@app.delete("/api/addresses/{address_id}")
def delete_address(address_id: int, me=Depends(require("customer"))):
    try:
        t.delete_address(address_id, me["customer_id"])
    except ValueError as e:
        raise HTTPException(404, str(e))
    return {"ok": True}


# --------------------------------------------------------------------------- #
# Kitchen (staff) routes — scoped to the staff member's branch
# --------------------------------------------------------------------------- #
@app.get("/api/kitchen/orders")
def kitchen_orders(include_delivered: bool = False, me=Depends(require("staff"))):
    return t.get_orders(me["branch_id"], include_delivered=include_delivered)


@app.post("/api/kitchen/orders/{order_id}/advance")
def kitchen_advance(order_id: int, me=Depends(require("staff"))):
    try:
        return {"status": t.advance_status(order_id)}
    except ValueError as e:
        raise HTTPException(404, str(e))


@app.get("/api/kitchen/stock")
def kitchen_stock(me=Depends(require("staff"))):
    return t.get_menu(me["branch_id"])


@app.post("/api/kitchen/restock")
def kitchen_restock(body: RestockBody, me=Depends(require("staff"))):
    try:
        return {"stock_quantity": t.restock(me["branch_id"], body.menu_id, body.amount)}
    except ValueError as e:
        raise HTTPException(400, str(e))


# --------------------------------------------------------------------------- #
# Delivery-partner routes — scoped to the partner's branch
# --------------------------------------------------------------------------- #
@app.get("/api/deliveries/available")
def deliveries_available(me=Depends(require("partner"))):
    return t.get_delivery_orders(me["branch_id"])


@app.get("/api/deliveries/mine")
def deliveries_mine(me=Depends(require("partner"))):
    return t.get_my_deliveries(me["partner_id"])


@app.post("/api/deliveries/{order_id}/accept")
def deliveries_accept(order_id: int, me=Depends(require("partner"))):
    try:
        t.claim_delivery(order_id, me["partner_id"])
    except t.DeliveryClaimError as e:
        raise HTTPException(409, str(e))
    return {"ok": True}


@app.post("/api/deliveries/{order_id}/deliver")
def deliveries_deliver(order_id: int, me=Depends(require("partner"))):
    try:
        t.mark_delivered(order_id, me["partner_id"])
    except ValueError as e:
        raise HTTPException(404, str(e))
    return {"ok": True}


@app.get("/api/health")
def health():
    return {"ok": True}


# Serve the built React app (react_app/frontend/dist) if present, so one uvicorn
# process serves both the UI and /api. Mounted last so the /api routes win.
_DIST = Path(__file__).resolve().parent.parent / "react_app" / "frontend" / "dist"
if _DIST.exists():
    app.mount("/", StaticFiles(directory=str(_DIST), html=True), name="spa")
