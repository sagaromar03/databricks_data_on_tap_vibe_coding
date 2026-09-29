import type {
  Branch, MenuItem, OrderResult, Session, KitchenOrder, DeliveryOrder, Address, CustomerOrder,
} from "./types";

// MOCK on = the whole UI runs standalone with sample data (no backend/DB),
// which is the default so it works anywhere. Run the real API instead with:
//   VITE_USE_MOCK=false npm run dev   (with uvicorn backend.api:app on :8000)
const MOCK = import.meta.env.VITE_USE_MOCK !== "false";

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
  const s: Session = { role: "customer", ...r.customer };
  session = s;
  return s;
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
  const s: Session = { role: "staff", ...r.staff };
  session = s;
  return s;
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
  const s: Session = { role: "partner", ...r.partner };
  session = s;
  return s;
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
    const total = +(subtotal + vat).toFixed(2);
    const order_id = Math.floor(Math.random() * 900 + 200);
    const nameById = Object.fromEntries(MENU.map((m) => [m.id, m.pizza_name]));
    const branch = BRANCHES.find((b) => b.branch_id === branchId)?.branch_name ?? "";
    MY_ORDERS.unshift({
      order_id, order_time: "just now", status: "order placed", delivery_mode: deliveryMode,
      total_price: total, branch_name: branch,
      items: items.map((i) => ({ pizza_name: nameById[i.menu_id], quantity: i.quantity })),
    });
    return { order_id, subtotal, vat_amount: vat, total_price: total };
  }
  return req("/api/orders", {
    method: "POST", body: JSON.stringify({ branch_id: branchId, items, delivery_mode: deliveryMode }),
  });
}

const ADDRESSES: Address[] = [
  { address_id: 1, label: "Home", street: "Gotgatan 12", city: "Stockholm", postal_code: "118 46" },
  { address_id: 2, label: "Work", street: "Sturegatan 4", city: "Stockholm", postal_code: "114 35" },
];
let nextAddressId = 3;
const MY_ORDERS: CustomerOrder[] = [
  {
    order_id: 42, order_time: "Sep 28 · 12:53", status: "delivered", delivery_mode: "delivery",
    total_price: 24.64, branch_name: "Pizza Hut Centrum",
    items: [{ pizza_name: "Pepperoni", quantity: 2 }],
  },
];

export async function getAddresses(): Promise<Address[]> {
  return MOCK ? ADDRESSES.map((a) => ({ ...a })) : req("/api/addresses");
}
export async function addAddress(a: Omit<Address, "address_id">): Promise<void> {
  if (MOCK) { ADDRESSES.push({ ...a, address_id: nextAddressId++ }); return; }
  await req("/api/addresses", { method: "POST", body: JSON.stringify(a) });
}
export async function updateAddress(id: number, a: Omit<Address, "address_id">): Promise<void> {
  if (MOCK) { Object.assign(ADDRESSES.find((x) => x.address_id === id)!, a); return; }
  await req(`/api/addresses/${id}`, { method: "PUT", body: JSON.stringify(a) });
}
export async function deleteAddress(id: number): Promise<void> {
  if (MOCK) { const i = ADDRESSES.findIndex((x) => x.address_id === id); if (i >= 0) ADDRESSES.splice(i, 1); return; }
  await req(`/api/addresses/${id}`, { method: "DELETE" });
}
export async function getMyOrders(): Promise<CustomerOrder[]> {
  return MOCK ? MY_ORDERS.map((o) => ({ ...o })) : req("/api/orders/mine");
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
