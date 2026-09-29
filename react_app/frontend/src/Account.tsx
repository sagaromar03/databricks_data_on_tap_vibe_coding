import type { Session } from "./types";
import { CustomerNav, CustomerPage } from "./ui";

export default function Account(
  { session, go, onLogout }: { session: Session; go: (p: CustomerPage) => void; onLogout: () => void },
) {
  const id = session.role === "customer" ? session.customer_id : "";
  const email = "email" in session ? session.email : "";
  return (
    <>
      <CustomerNav page="account" go={go} onLogout={onLogout} />
      <div className="wrap">
        <h2>Account</h2>
        <div className="summary" style={{ maxWidth: 460 }}>
          <div className="t"><span>Customer ID</span><span>#{id}</span></div>
          <div className="t"><span>Name</span><span>{session.name}</span></div>
          <div className="t"><span>Email</span><span>{email}</span></div>
        </div>
      </div>
    </>
  );
}
