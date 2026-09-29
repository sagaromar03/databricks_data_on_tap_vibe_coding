import { useEffect, useState } from "react";
import type { Address, Session } from "./types";
import * as api from "./api";
import { CustomerNav, CustomerPage } from "./ui";

const blank = { label: "Home", street: "", city: "", postal_code: "" };

const EditIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 20h9" /><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z" />
  </svg>
);
const DeleteIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M3 6h18" /><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
    <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" /><path d="M10 11v6M14 11v6" />
  </svg>
);

export default function Addresses(
  { go, onLogout }: { session: Session; go: (p: CustomerPage) => void; onLogout: () => void },
) {
  const [list, setList] = useState<Address[]>([]);
  const [editing, setEditing] = useState<number | "new" | null>(null);
  const [form, setForm] = useState<Omit<Address, "address_id">>(blank);
  const [error, setError] = useState("");

  const load = () => api.getAddresses().then(setList);
  useEffect(() => { load(); }, []);

  const startAdd = () => { setForm(blank); setEditing("new"); setError(""); };
  const startEdit = (a: Address) => {
    setForm({ label: a.label, street: a.street, city: a.city, postal_code: a.postal_code });
    setEditing(a.address_id); setError("");
  };
  const cancel = () => setEditing(null);

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.street.trim() || !form.city.trim()) { setError("Street and city are required."); return; }
    if (editing === "new") await api.addAddress(form);
    else if (typeof editing === "number") await api.updateAddress(editing, form);
    setEditing(null); load();
  };
  const remove = async (id: number) => { await api.deleteAddress(id); load(); };

  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.value }));

  return (
    <>
      <CustomerNav page="addresses" go={go} onLogout={onLogout} />
      <div className="wrap">
        <h2>Addresses</h2>

        {editing !== null ? (
          <form className="card form" style={{ maxWidth: 460 }} onSubmit={save}>
            <h3 style={{ margin: "0 0 6px" }}>{editing === "new" ? "Add address" : "Edit address"}</h3>
            <label>Label</label><input value={form.label} onChange={set("label")} />
            <label>Street</label><input value={form.street} onChange={set("street")} />
            <label>City</label><input value={form.city} onChange={set("city")} />
            <label>Postal code</label><input value={form.postal_code} onChange={set("postal_code")} />
            <div className="acceptrow" style={{ marginTop: 12 }}>
              <button className="add" type="submit">Save</button>
              <button className="ghost" type="button" onClick={cancel}>Cancel</button>
            </div>
            {error && <div className="err">{error}</div>}
          </form>
        ) : (
          <>
            <button className="add" style={{ width: "auto", marginBottom: 14 }} onClick={startAdd}>＋ Add address</button>
            <div className="stack">
              {list.length === 0 && <div className="empty">No saved addresses yet.</div>}
              {list.map((a) => (
                <div className="card ord" key={a.address_id}>
                  <div>
                    <div className="ord-head">{a.label || "Address"}</div>
                    <div className="ord-meta">{a.street}, {a.postal_code} {a.city}</div>
                  </div>
                  <div className="iconrow">
                    <button className="iconbtn" title="Edit" aria-label="Edit" onClick={() => startEdit(a)}><EditIcon /></button>
                    <button className="iconbtn danger" title="Delete" aria-label="Delete" onClick={() => remove(a.address_id)}><DeleteIcon /></button>
                  </div>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </>
  );
}
