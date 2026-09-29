export const money = (n: number) => n.toFixed(2) + " kr";

export function statusPill(status: string): string {
  const cls = "status-" + status.replace(/ /g, "-");
  return `<span class='status ${cls}'>${status}</span>`;
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
