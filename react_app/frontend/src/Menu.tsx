import { useEffect, useMemo, useState } from "react";
import type { Branch, MenuItem, Session } from "./types";
import * as api from "./api";
import { pizzaSvg } from "./pizza";
import { money, CustomerNav, CustomerPage } from "./ui";

const dietClass = (d: string) => (d === "vegan" ? "vegan" : d === "non-veg" ? "nonveg" : "veg");
const Svg = ({ name, diet, size }: { name: string; diet: string; size: number }) => (
  <span style={{ width: size, height: size, flex: "0 0 auto", display: "inline-block" }}
    dangerouslySetInnerHTML={{ __html: pizzaSvg(name, diet) }} />
);

export default function Menu(
  { go, onLogout }: { session: Session; go: (p: CustomerPage) => void; onLogout: () => void },
) {
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
  const cartBtn = (
    <button className="cartbtn" onClick={() => setOpen(true)}>🛒 Cart
      {count > 0 && <span className="badge">{count}</span>}</button>
  );

  return (
    <>
      <CustomerNav page="menu" go={go} onLogout={onLogout} right={cartBtn} />
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
