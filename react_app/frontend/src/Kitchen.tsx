import { useEffect, useState } from "react";
import type { KitchenOrder, MenuItem, Session } from "./types";
import * as api from "./api";
import { Header, statusPill, money } from "./ui";

export default function Kitchen({ session, onLogout }: { session: Session; onLogout: () => void }) {
  const [tab, setTab] = useState<"queue" | "stock">("queue");
  const [orders, setOrders] = useState<KitchenOrder[]>([]);
  const [stock, setStock] = useState<MenuItem[]>([]);
  const [amounts, setAmounts] = useState<Record<number, number>>({});

  const load = () => { api.getKitchenOrders().then(setOrders); api.getStock().then(setStock); };
  useEffect(load, []);

  const advance = async (id: number) => { await api.advanceStatus(id); load(); };
  const doRestock = async (id: number) => { await api.restock(id, amounts[id] ?? 5); load(); };

  const branch = "branch_name" in session ? session.branch_name : "";

  return (
    <>
      <Header title="Kitchen" subtitle={`${branch} · ${session.name}`} onLogout={onLogout} />
      <div className="wrap">
        <div className="tabs">
          <button className={tab === "queue" ? "on" : ""} onClick={() => setTab("queue")}>Order queue</button>
          <button className={tab === "stock" ? "on" : ""} onClick={() => setTab("stock")}>Stock &amp; restock</button>
        </div>

        {tab === "queue" && (
          <div className="stack">
            {orders.length === 0 && <div className="empty">No orders in the queue.</div>}
            {orders.map((o) => (
              <div className="card ord" key={o.order_id}>
                <div>
                  <div className="ord-head">Order #{o.order_id} <span dangerouslySetInnerHTML={{ __html: statusPill(o.status) }} /></div>
                  <div className="ord-meta">{o.customer_name} · {o.delivery_mode} · {o.order_time}</div>
                  <div className="ord-items">{o.items.map((i) => `${i.quantity}× ${i.pizza_name}`).join(", ")}</div>
                  <span className="price">{money(o.total_price)}</span>
                </div>
                {o.status !== "delivered" && <button className="add" onClick={() => advance(o.order_id)}>Advance ▶</button>}
              </div>
            ))}
          </div>
        )}

        {tab === "stock" && (
          <div className="stack">
            {stock.map((m) => (
              <div className="card ord" key={m.id}>
                <div><div className="ord-head">{m.pizza_name}</div>
                  <div className="ord-meta">{m.stock_quantity} in stock</div></div>
                <div className="restock">
                  <input type="number" min={1} value={amounts[m.id] ?? 5}
                    onChange={(e) => setAmounts((a) => ({ ...a, [m.id]: +e.target.value }))} />
                  <button className="ghost" onClick={() => doRestock(m.id)}>Restock</button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </>
  );
}
