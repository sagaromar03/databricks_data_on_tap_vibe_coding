import type {
  Branch, MenuItem, OrderResult, Session, KitchenOrder, DeliveryOrder,
} from "./types";

// MOCK = true runs the whole UI standalone (sample data, no backend/DB) — for
// local dev and previews. Flip to false to call backend/api.py over HTTP.
const MOCK = true;

let token: string | null = null;
let session: Session | null = null;
export function setToken(t: string | null) { token = t; }
export function clearSession() { token = null; session = null; }

async function req<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const res = await fetch(path, {
    ...opts,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(opts.headers ?? {}),
    },
  });
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail ?? res.statusText);
  return res.json();
}

// --------------------------------------------------------------------------- //
// Mock data (mutable, so accept/advance/restock reflect on screen)
// --------------------------------------------------------------------------- //
const BRANCHES: Branch[] = [
  { branch_id: 1, branch_name: "Pizza Hut Sodermalm", city: "Stockholm" },
  { branch_id: 2, branch_name: "Pizza Hut Ostermalm", city: "Stockholm" },
  { branch_id: 3, branch_name: "Pizza Hut Centrum", city: "Goteborg" },
];
const MENU: MenuItem[] = [
  { id: 1, pizza_name: "Margherita", price: 9.0, diet_type: "veg", stock_quantity: 20 },
  { id: 2, pizza_name: "Four Cheese", price: 11.0, diet_type: "veg", stock_quantity: 14 },
  { id: 3, pizza_name: "Veggie Supreme", price: 11.5, diet_type: "veg", stock_quantity: 12 },
  { id: 4, pizza_name: "Vegan Garden", price: 12.0, diet_type: "vegan", stock_quantity: 6 },
  { id: 5, pizza_name: "Pepperoni", price: 11.0, diet_type: "non-veg", stock_quantity: 3 },
  { id: 6, pizza_name: "BBQ Chicken", price: 12.5, diet_type: "non-veg", stock_quantity: 2 },
];
const STATUS_FLOW = ["order placed", "preparing", "packed", "delivered"];
type Internal = KitchenOrder & { branch_id: number; partner_id: number | null };
let ORDERS: Internal[] = [
  {
    order_id: 100, branch_id: 3, partner_id: null,
    order_time: "12:53", status: "packed", delivery_mode: "delivery",
    total_price: 24.64, customer_name: "Erik Lindqvist",
    items: [{ pizza_name: "Pepperoni", quantity: 2 }],
  },
  {
    order_id: 101, branch_id: 3, partner_id: null,
    order_time: "13:10", status: "preparing", delivery_mode: "pickup",
    total_price: 10.08, customer_name: "Sara Johansson",
    items: [{ pizza_name: "Margherita", quantity: 1 }],
  },
];

// --------------------------------------------------------------------------- //
// Public reads
// --------------------------------------------------------------------------- //
export async function getBranches(): Promise<Branch[]> {
  return MOCK ? BRANCHES : req("/api/branches");
}
export async function getMenu(branchId: number): Promise<MenuItem[]> {
  return MOCK ? MENU.map((m) => ({ ...m })) : req(`/api/menu?branch_id=${branchId}`);
}

// --------------------------------------------------------------------------- //
// Auth (returns a Session and, in real mode, stores the JWT)
// --------------------------------------------------------------------------- //
export async function login(email: string, password: string): Promise<Session> {
  if (MOCK) {
    if (password !== "pizza") throw new Error("Invalid email or password.");
    session = { role: "customer", customer_id: 1, name: email.split("@")[0] || "Guest", email };
    return session;
  }
  const r = await req<{ token: string; customer: any }>("/api/auth/login", {
    method: "POST", body: JSON.stringify({ email, password }),
  });
  setToken(r.token);
  session = { role: "customer", ...r.customer };
  return session;
}
export async function staffLogin(email: string, password: string): Promise<Session> {
  if (MOCK) {
    if (password !== "kitchen") throw new Error("Invalid email or password.");
    session = { role: "staff", staff_id: 1, name: "Goteborg Kitchen", branch_id: 3, branch_name: "Pizza Hut Centrum" };
    return session;
  }
  const r = await req<{ token: string; staff: any }>("/api/auth/staff/login", {
    method: "POST", body: JSON.stringify({ email, password }),
  });
  setToken(r.token);
  session = { role: "staff", ...r.staff };
  return session;
}
export async function partnerLogin(email: string, password: string): Promise<Session> {
  if (MOCK) {
    if (password !== "partner") throw new Error("Invalid email or password.");
    session = { role: "partner", partner_id: 3, name: "Nils Ek", branch_id: 3, branch_name: "Pizza Hut Centrum" };
    return session;
  }
  const r = await req<{ token: string; partner: any }>("/api/auth/partner/login", {
    method: "POST", body: JSON.stringify({ email, password }),
  });
  setToken(r.token);
  session = { role: "partner", ...r.partner };
  return session;
}

// --------------------------------------------------------------------------- //
// Customer
// --------------------------------------------------------------------------- //
export async function placeOrder(
  branchId: number, items: { menu_id: number; quantity: number }[], deliveryMode: string,
): Promise<OrderResult> {
  if (MOCK) {
    const priceById = Object.fromEntries(MENU.map((m) => [m.id, m.price]));
    for (const it of items) {
      const m = MENU.find((x) => x.id === it.menu_id)!;
      if (m.stock_quantity < it.quantity) throw new Error(`Sold out: ${m.pizza_name}`);
    }
    for (const it of items) MENU.find((x) => x.id === it.menu_id)!.stock_quantity -= it.quantity;
    const subtotal = items.reduce((a, i) => a + priceById[i.menu_id] * i.quantity, 0);
    const vat = +(subtotal * 0.12).toFixed(2);
    return { order_id: Math.floor(Math.random() * 900 + 200), subtotal, vat_amount: vat, total_price: +(subtotal + vat).toFixed(2) };
  }
  return req("/api/orders", {
    method: "POST", body: JSON.stringify({ branch_id: branchId, items, delivery_mode: deliveryMode }),
  });
}

// --------------------------------------------------------------------------- //
// Kitchen (staff)
// --------------------------------------------------------------------------- //
export async function getKitchenOrders(): Promise<KitchenOrder[]> {
  if (MOCK) {
    const b = session && "branch_id" in session ? session.branch_id : 3;
    return ORDERS.filter((o) => o.branch_id === b && !["delivered", "out for delivery"].includes(o.status))
      .map(({ branch_id, partner_id, ...k }) => k);
  }
  return req("/api/kitchen/orders");
}
export async function advanceStatus(orderId: number): Promise<string> {
  if (MOCK) {
    const o = ORDERS.find((x) => x.order_id === orderId)!;
    const i = STATUS_FLOW.indexOf(o.status);
    if (i >= 0 && i < STATUS_FLOW.length - 1) o.status = STATUS_FLOW[i + 1];
    return o.status;
  }
  return (await req<{ status: string }>(`/api/kitchen/orders/${orderId}/advance`, { method: "POST" })).status;
}
export async function getStock(): Promise<MenuItem[]> {
  return MOCK ? MENU.map((m) => ({ ...m })) : req("/api/kitchen/stock");
}
export async function restock(menuId: number, amount: number): Promise<number> {
  if (MOCK) {
    const m = MENU.find((x) => x.id === menuId)!;
    m.stock_quantity += amount;
    return m.stock_quantity;
  }
  return (await req<{ stock_quantity: number }>("/api/kitchen/restock", {
    method: "POST", body: JSON.stringify({ menu_id: menuId, amount }),
  })).stock_quantity;
}

// --------------------------------------------------------------------------- //
// Delivery partner
// --------------------------------------------------------------------------- //
function asDelivery(o: Internal): DeliveryOrder {
  return { order_id: o.order_id, order_time: o.order_time, status: o.status, total_price: o.total_price, customer_name: o.customer_name };
}
export async function getAvailableDeliveries(): Promise<DeliveryOrder[]> {
  if (MOCK) {
    const b = session && "branch_id" in session ? session.branch_id : 3;
    return ORDERS.filter((o) => o.branch_id === b && o.delivery_mode === "delivery"
      && o.partner_id === null && !["delivered", "out for delivery"].includes(o.status)).map(asDelivery);
  }
  return req("/api/deliveries/available");
}
export async function getMyDeliveries(): Promise<DeliveryOrder[]> {
  if (MOCK) {
    const pid = session && session.role === "partner" ? session.partner_id : -1;
    return ORDERS.filter((o) => o.partner_id === pid && o.status === "out for delivery").map(asDelivery);
  }
  return req("/api/deliveries/mine");
}
export async function acceptDelivery(orderId: number): Promise<void> {
  if (MOCK) {
    const o = ORDERS.find((x) => x.order_id === orderId)!;
    if (o.partner_id !== null) throw new Error("Order was already taken by another partner.");
    o.partner_id = session && session.role === "partner" ? session.partner_id : 0;
    o.status = "out for delivery";
    return;
  }
  await req(`/api/deliveries/${orderId}/accept`, { method: "POST" });
}
export async function markDelivered(orderId: number): Promise<void> {
  if (MOCK) { ORDERS.find((x) => x.order_id === orderId)!.status = "delivered"; return; }
  await req(`/api/deliveries/${orderId}/deliver`, { method: "POST" });
}
