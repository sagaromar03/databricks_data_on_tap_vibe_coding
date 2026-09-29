import { useState } from "react";
import type { Role, Session } from "./types";
import * as api from "./api";
import { pizzaSvg } from "./pizza";
import Customer from "./Customer";
import Kitchen from "./Kitchen";
import Deliveries from "./Deliveries";

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

export default function App() {
  const [session, setSession] = useState<Session | null>(null);
  const logout = () => { api.clearSession(); setSession(null); };
  if (!session) return <Login onLogin={setSession} />;
  if (session.role === "staff") return <Kitchen session={session} onLogout={logout} />;
  if (session.role === "partner") return <Deliveries session={session} onLogout={logout} />;
  return <Customer session={session} onLogout={logout} />;
}
