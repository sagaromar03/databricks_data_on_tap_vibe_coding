export const money = (n: number) => n.toFixed(2) + " kr";

export function statusPill(status: string): string {
  const cls = "status-" + status.replace(/ /g, "-");
  return `<span class='status ${cls}'>${status}</span>`;
}

export type CustomerPage = "menu" | "account" | "addresses" | "orders";

export function CustomerNav(
  { page, go, onLogout, right }:
  { page: CustomerPage; go: (p: CustomerPage) => void; onLogout: () => void; right?: React.ReactNode },
) {
  const links: [CustomerPage, string][] = [
    ["menu", "Menu"], ["account", "Account"], ["addresses", "Addresses"], ["orders", "Order history"],
  ];
  return (
    <div className="topbar">
      <div className="navleft">
        <span className="brand">🍕 Data on <span className="a">Tap</span></span>
        <nav className="navlinks">
          {links.map(([k, label]) => (
            <button key={k} className={page === k ? "navlink on" : "navlink"} onClick={() => go(k)}>{label}</button>
          ))}
        </nav>
      </div>
      <div className="navright">{right}<button className="ghost" onClick={onLogout}>Log out</button></div>
    </div>
  );
}

export function Header({ title, subtitle, onLogout }: { title: string; subtitle: string; onLogout: () => void }) {
  return (
    <div className="topbar">
      <div>
        <span className="brand">🍕 Data on <span className="a">Tap</span></span>
        <span className="pill">{title} · {subtitle}</span>
      </div>
      <button className="ghost" onClick={onLogout}>Log out</button>
    </div>
  );
}
