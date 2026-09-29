import { useState } from "react";
import type { Session } from "./types";
import type { CustomerPage } from "./ui";
import Menu from "./Menu";
import Account from "./Account";
import Addresses from "./Addresses";
import OrderHistory from "./OrderHistory";

export default function Customer({ session, onLogout }: { session: Session; onLogout: () => void }) {
  const [page, setPage] = useState<CustomerPage>("menu");
  const props = { session, go: setPage, onLogout };
  if (page === "account") return <Account {...props} />;
  if (page === "addresses") return <Addresses {...props} />;
  if (page === "orders") return <OrderHistory {...props} />;
  return <Menu {...props} />;
}
