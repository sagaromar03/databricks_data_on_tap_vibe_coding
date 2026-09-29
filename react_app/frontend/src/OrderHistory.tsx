import { useEffect, useState } from "react";
import type { CustomerOrder, Session } from "./types";
import * as api from "./api";
import { CustomerNav, CustomerPage, statusPill, money } from "./ui";

export default function OrderHistory(
  { go, onLogout }: { session: Session; go: (p: CustomerPage) => void; onLogout: () => void },
) {
  const [orders, setOrders] = useState<CustomerOrder[]>([]);
  useEffect(() => { api.getMyOrders().then(setOrders); }, []);

  return (
    <>
      <CustomerNav page="orders" go={go} onLogout={onLogout} />
      <div className="wrap">
        <h2>Order history</h2>
        <div className="stack">
          {orders.length === 0 && <div className="empty">No orders yet.</div>}
          {orders.map((o) => (
            <div className="card" key={o.order_id}>
              <div className="ord-head">Order #{o.order_id} <span dangerouslySetInnerHTML={{ __html: statusPill(o.status) }} /></div>
              <div className="ord-meta">{o.branch_name} · {o.delivery_mode} · {o.order_time}</div>
              <div className="ord-items">{o.items.map((i) => `${i.quantity}× ${i.pizza_name}`).join(", ")}</div>
              <span className="price">{money(o.total_price)}</span>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}
