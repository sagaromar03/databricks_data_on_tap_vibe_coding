import { useEffect, useMemo, useState } from "react";
import type { Branch, MenuItem, Role, Session } from "./types";
import * as api from "./api";
import { pizzaSvg } from "./pizza";
import { money } from "./ui";
import Kitchen from "./Kitchen";
import Deliveries from "./Deliveries";

const dietClass = (d: string) => (d === "vegan" ? "vegan" : d === "non-veg" ? "nonveg" : "veg");
const Svg = ({ name, diet, size }: { name: string; diet: string; size: number }) => (
  <span style={{ width: size, height: size, flex: "0 0 auto", display: "inline-block" }}
    dangerouslySetInnerHTML={{ __html: pizzaSvg(name, diet) }} />
);

const DEMO: Record<Role, { email: string; password: string; label: string }> = {
  customer: { email: "anna@example.se", password: "pizza", label: "Customer" },
  staff: { email: "kitchen.goteborg@dataontap.se", password: "kitchen", label: "Kitchen" },
  partner: { email: "nils@dataontap.se", password: "partner", label: "Delivery partner" },
};

function Login({ onLogin }: { onLogin: (s: Session) => void }) {
  const [role, setRole] = useState<Role>("customer");
  const [email, setEmail] = useState(DEMO.customer.email);
  const [password, setPassword] = useState(DEMO.customer.password);
  const [error, setError] = useState("");

  const pickRole = (r: Role) => { setRole(r); setEmail(DEMO[r].email); setPassword(DEMO[r].password); setError(""); };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    try {
      const fn = role === "staff" ? api.staffLogin : role === "partner" ? api.partnerLogin : api.login;
      onLogin(await fn(email, password));
    } catch (err) { setError((err as Error).message); }
  };

  return (
    <div className="split">
      <div className="split-left">
        <div className="banner-pizza" dangerouslySetInnerHTML={{ __html: pizzaSvg("pepperoni", "non-veg") }} />
        <div>
          <div className="eyebrow">Pizza ordering on Lakebase</div>
          <h1>Data on Tap</h1>
          <p>Order from your nearest branch — a real React frontend on the same backend.</p>
        </div>
        <div className="poweredby">Powered by Databricks</div>
      </div>
      <div className="split-right">
        <h2 className="rhead">Sign in</h2>
        <form onSubmit={submit} className="card form">
          <label>Sign in as</label>
          <select value={role} onChange={(e) => pickRole(e.target.value as Role)}>
            <option value="customer">Customer</option>
            <option value="staff">Kitchen</option>
            <option value="partner">Delivery partner</option>
          </select>
          <label>Email</label>
          <input value={email} onChange={(e) => setEmail(e.target.value)} />
          <label>Password</label>
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
          <button className="primary" type="submit">Log in as {DEMO[role].label}</button>
          {error && <div className="err">{error}</div>}
        </form>
        <div className="demo">Demo: {DEMO[role].email} / {DEMO[role].password}</div>
      </div>
    </div>
  );
}

function Menu({ session, onLogout }: { session: Session; onLogout: () => void }) {
  const [branches, setBranches] = useState<Branch[]>([]);
  const [branchId, setBranchId] = useState(1);
  const [menu, setMenu] = useState<MenuItem[]>([]);
  const [cart, setCart] = useState<Record<number, number>>({});
  const [mode, setMode] = useState("pickup");
  const [open, setOpen] = useState(false);
  const [toast, setToast] = useState("");

  useEffect(() => { api.getBranches().then(setBranches); }, []);
  useEffect(() => { api.getMenu(branchId).then(setMenu); }, [branchId]);

  const change = (m: MenuItem, d: number) =>
    setCart((c) => ({ ...c, [m.id]: Math.max(0, Math.min(m.stock_quantity, (c[m.id] || 0) + d)) }));

  const lines = useMemo(
    () => menu.filter((m) => (cart[m.id] || 0) > 0).map((m) => ({ m, q: cart[m.id] })),
    [menu, cart],
  );
  const subtotal = lines.reduce((a, l) => a + l.m.price * l.q, 0);
  const vat = +(subtotal * 0.12).toFixed(2);
  const total = +(subtotal + vat).toFixed(2);
  const count = lines.reduce((a, l) => a + l.q, 0);

  const place = async () => {
    const res = await api.placeOrder(branchId, lines.map((l) => ({ menu_id: l.m.id, quantity: l.q })), mode);
    setCart({}); setOpen(false);
    setToast(`Order #${res.order_id} placed — ${money(res.total_price)}. Enjoy!`);
    setTimeout(() => setToast(""), 2600);
    api.getMenu(branchId).then(setMenu);
  };

  const cities = [...new Set(branches.map((b) => b.city))];

  return (
    <>
      <div className="topbar">
        <div><span className="brand">🍕 Data on <span className="a">Tap</span></span>
          <span className="pill">Signed in as {session.name}</span></div>
        <div>
          <button className="ghost" onClick={onLogout}>Log out</button>
          <button className="cartbtn" onClick={() => setOpen(true)}>🛒 Cart
            {count > 0 && <span className="badge">{count}</span>}</button>
        </div>
      </div>

      <div className="wrap">
        <div className="row">
          <div><label>City</label>
            <select onChange={(e) => {
              const first = branches.find((b) => b.city === e.target.value);
              if (first) setBranchId(first.branch_id);
            }}>{cities.map((c) => <option key={c}>{c}</option>)}</select></div>
          <div><label>Branch</label>
            <select value={branchId} onChange={(e) => setBranchId(+e.target.value)}>
              {branches.map((b) => <option key={b.branch_id} value={b.branch_id}>{b.branch_name}</option>)}
            </select></div>
          <div><label>Delivery</label>
            <select value={mode} onChange={(e) => setMode(e.target.value)}>
              <option>pickup</option><option>delivery</option></select></div>
        </div>

        <h2>Menu</h2>
        <div className="grid">
          {menu.map((m) => (
            <div className="card" key={m.id}>
              <div className="pzrow"><Svg name={m.pizza_name} diet={m.diet_type} size={38} />
                <div className="name">{m.pizza_name} <span className={`badge2 ${dietClass(m.diet_type)}`}>{m.diet_type}</span></div></div>
              <div><span className="price">{money(m.price)}</span>{" · "}
                <span className={"stock" + (m.stock_quantity <= 3 ? " low" : "")}>{m.stock_quantity} left</span></div>
              {(cart[m.id] || 0) > 0 ? (
                <div className="qtyctl">
                  <button onClick={() => change(m, -1)}>−</button><b>{cart[m.id]}</b><button onClick={() => change(m, 1)}>+</button>
                </div>
              ) : (
                <button className="add" disabled={m.stock_quantity === 0} onClick={() => change(m, 1)}>
                  {m.stock_quantity === 0 ? "Sold out" : "Add to cart"}</button>
              )}
            </div>
          ))}
        </div>
      </div>

      {open && <div className="scrim on" onClick={() => setOpen(false)} />}
      <div className={"drawer" + (open ? " open" : "")}>
        <h3>Your order</h3>
        <div className="items">
          {lines.length === 0 ? <div className="empty">Your cart is empty.</div>
            : lines.map((l) => (
              <div className="line" key={l.m.id}><span><span className="q">{l.q} ×</span> {l.m.pizza_name}</span>
                <span>{money(l.m.price * l.q)}</span></div>))}
        </div>
        <div className="totals">
          <div className="t"><span>Subtotal</span><span>{money(subtotal)}</span></div>
          <div className="t"><span>VAT (12%)</span><span>{money(vat)}</span></div>
          <div className="t grand"><span>Total</span><span>{money(total)}</span></div>
          <button className="primary" disabled={count === 0} onClick={place}>Place order</button>
        </div>
      </div>

      {toast && <div className="toast show">✓ {toast}</div>}
    </>
  );
}

export default function App() {
  const [session, setSession] = useState<Session | null>(null);
  const logout = () => { api.clearSession(); setSession(null); };
  if (!session) return <Login onLogin={setSession} />;
  if (session.role === "staff") return <Kitchen session={session} onLogout={logout} />;
  if (session.role === "partner") return <Deliveries session={session} onLogout={logout} />;
  return <Menu session={session} onLogout={logout} />;
}
