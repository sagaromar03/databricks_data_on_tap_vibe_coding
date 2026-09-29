import { useEffect, useState } from "react";
import type { DeliveryOrder, Session } from "./types";
import * as api from "./api";
import { Header, statusPill, money } from "./ui";

export default function Deliveries({ session, onLogout }: { session: Session; onLogout: () => void }) {
  const [available, setAvailable] = useState<DeliveryOrder[]>([]);
  const [mine, setMine] = useState<DeliveryOrder[]>([]);
  const [passed, setPassed] = useState<Set<number>>(new Set());
  const [note, setNote] = useState("");

  const load = () => { api.getAvailableDeliveries().then(setAvailable); api.getMyDeliveries().then(setMine); };
  useEffect(load, []);

  const accept = async (id: number) => {
    try { await api.acceptDelivery(id); load(); }
    catch (e) { setNote((e as Error).message); setTimeout(() => setNote(""), 2500); load(); }
  };
  const deliver = async (id: number) => { await api.markDelivered(id); load(); };
  const reject = (id: number) => setPassed((p) => new Set(p).add(id));

  const branch = "branch_name" in session ? session.branch_name : "";
  const avail = available.filter((o) => !passed.has(o.order_id));

  const card = (o: DeliveryOrder) => (
    <div key={o.order_id}>
      <div className="ord-head">Order #{o.order_id} <span dangerouslySetInnerHTML={{ __html: statusPill(o.status) }} /></div>
      <div className="ord-meta">{o.customer_name} · {o.order_time}</div>
      <span className="price">{money(o.total_price)}</span>
    </div>
  );

  return (
    <>
      <Header title="Deliveries" subtitle={`${branch} · ${session.name}`} onLogout={onLogout} />
      <div className="wrap">
        <h2>Out for delivery</h2>
        <div className="stack">
          {mine.length === 0 && <div className="empty">Nothing out for delivery right now.</div>}
          {mine.map((o) => (
            <div className="card ord" key={o.order_id}>{card(o)}
              <button className="add" onClick={() => deliver(o.order_id)}>Mark delivered</button></div>
          ))}
        </div>

        <h2>Available deliveries — {avail.length}</h2>
        <div className="stack">
          {avail.length === 0 && <div className="card"><div className="ord-head">All caught up 🎉</div>
            <div className="ord-meta">No deliveries to accept right now.</div></div>}
          {avail.map((o) => (
            <div className="card ord" key={o.order_id}>{card(o)}
              <div className="acceptrow">
                <button className="add" onClick={() => accept(o.order_id)}>Accept</button>
                <button className="ghost" onClick={() => reject(o.order_id)}>Reject</button>
              </div></div>
          ))}
        </div>
      </div>
      {note && <div className="toast show">⚠ {note}</div>}
    </>
  );
}
