"""Presentation layer for Data on Tap — CSS and small HTML render helpers.

Isolated from logic: this module holds zero business logic and no DB calls. It
only turns values into styled markup. app.py imports it for the polish pass.
"""

from decimal import Decimal

CSS = """
<style>
:root {
  --accent: #FF5A3C;
  --surface: #241C18;
  --border: #3A2E28;
  --text: #F3ECE6;
  --muted: #B7A99E;
  --ok: #5FB878;
  --low: #E8A13A;
  --out: #8A7B72;
}

/* Tighten the top padding and widen a touch */
.block-container { padding-top: 2.2rem; max-width: 1100px; }

/* Landing brand */
.brand { font-size: 2.6rem; font-weight: 800; letter-spacing: -.02em; }
.brand .accent { color: var(--accent); }
.brand-sub { color: var(--muted); font-size: 1.05rem; margin: .1rem 0 1.4rem; }

/* Split landing — branded left panel */
.split-left {
  background: linear-gradient(160deg, #FF6B35 0%, #E23E2C 55%, #B4271A 100%);
  border-radius: 20px;
  padding: 3rem 2.6rem;
  min-height: 78vh;
  color: #fff;
  display: flex; flex-direction: column; justify-content: space-between;
  position: relative; overflow: hidden;
  box-shadow: 0 12px 34px rgba(226,62,44,.28);
}
/* The big corner slice (SVG) — resting position. */
.split-left .banner-pizza {
  position: absolute; right: 1.4rem; bottom: 1.4rem; width: 160px; height: 160px;
  transform: rotate(-10deg); opacity: .96;
  filter: drop-shadow(0 10px 16px rgba(0,0,0,.28));
}
.split-left .banner-pizza svg { width: 100%; height: 100%; display: block; }
/* One-shot entrance on first load only (class added just once), then it stops. */
.split-left.animate-in .banner-pizza {
  animation: pizza-enter 1.4s cubic-bezier(.22,.61,.36,1) both;
}
@keyframes pizza-enter {
  from { transform: translate(150px, 150px) rotate(70deg) scale(1.4); opacity: 0; }
  to   { transform: translate(0, 0) rotate(-10deg) scale(1); opacity: .96; }
}
/* Inline slice on menu cards */
.pizza-ico { flex: 0 0 auto; }
.menu-row { display: flex; gap: 12px; align-items: center; }
.split-left .eyebrow { text-transform: uppercase; letter-spacing: .12em;
  font-size: .74rem; font-weight: 700; opacity: .85; }
.split-left h1 { font-size: 2.7rem; line-height: 1.05; margin: .4rem 0 0; letter-spacing: -.02em; }
.split-left p { font-size: 1.08rem; opacity: .95; margin: .7rem 0 0; max-width: 26rem; }
.poweredby { display: flex; align-items: center; gap: .5rem; font-size: .92rem;
  opacity: .95; margin-top: 1.6rem; position: relative; z-index: 1; }
.poweredby svg { display: block; }
.right-head { font-weight: 800; font-size: 1.35rem; margin: .2rem 0 .2rem; }
.right-sub { color: var(--muted); margin-bottom: 1rem; }

/* Landing hero banner */
.banner {
  position: relative;
  background: linear-gradient(135deg, #FF6B35 0%, #E23E2C 55%, #B4271A 100%);
  border-radius: 20px;
  padding: 3.2rem 2.6rem;
  margin: .2rem 0 1.6rem;
  color: #fff;
  overflow: hidden;
  box-shadow: 0 12px 34px rgba(226,62,44,.28);
}
.banner::after {
  content: "🍕";
  position: absolute;
  right: 1.4rem; bottom: -1.2rem;
  font-size: 8rem;
  opacity: .18;
  transform: rotate(-12deg);
}
.banner .eyebrow { text-transform: uppercase; letter-spacing: .12em; font-size: .75rem;
  font-weight: 700; opacity: .85; }
.banner h1 { font-size: 2.9rem; line-height: 1.05; margin: .35rem 0 0; letter-spacing: -.02em; }
.banner p { font-size: 1.15rem; opacity: .95; margin: .6rem 0 0; max-width: 34rem; }
.nav-brand { font-weight: 800; font-size: 1.15rem; padding-top: .35rem; }

/* Page hero */
.hero { display: flex; align-items: baseline; gap: .6rem; margin-bottom: .2rem; }
.hero h1 { font-size: 2.1rem; margin: 0; letter-spacing: -.02em; }
.hero .sub { color: var(--muted); font-size: .95rem; }

/* Menu item card text */
.pizza-name { font-weight: 700; font-size: 1.05rem; }
.item-sub { margin-top: .35rem; display: flex; align-items: center; gap: .6rem; }
.price { color: var(--text); font-weight: 600; }

/* Badges + pills */
.badge, .pill, .status {
  display: inline-block; padding: .12rem .55rem; border-radius: 999px;
  font-size: .72rem; font-weight: 700; letter-spacing: .02em; line-height: 1.5;
}
.badge-veg     { background: rgba(95,184,120,.16);  color: #7ED396; }
.badge-vegan   { background: rgba(43,179,163,.16);   color: #46C9BA; }
.badge-nonveg  { background: rgba(226,87,76,.16);    color: #F0857B; }

.pill-ok  { background: rgba(95,184,120,.16); color: #7ED396; }
.pill-low { background: rgba(232,161,58,.18); color: #F0B75E; }
.pill-out { background: rgba(138,123,114,.20); color: var(--muted); }

/* Order summary card */
.summary { background: var(--surface); border: 1px solid var(--border);
  border-radius: 14px; padding: 1rem 1.1rem; }
.summary .row { display: flex; justify-content: space-between; padding: .28rem 0;
  color: var(--muted); }
.summary .row span:last-child { color: var(--text); font-weight: 600; }
.summary .row.total { border-top: 1px solid var(--border); margin-top: .4rem;
  padding-top: .6rem; font-size: 1.15rem; }
.summary .row.total span { color: var(--text); font-weight: 800; }
.summary .row.total span:last-child { color: var(--accent); }

/* Cart lines */
.cart-line { display: flex; justify-content: space-between; padding: .2rem 0;
  color: var(--text); }
.cart-line .q { color: var(--muted); }

/* Kitchen order card */
.order-head { font-weight: 700; font-size: 1.02rem; }
.order-meta { color: var(--muted); font-size: .85rem; margin: .1rem 0 .5rem; }
.order-items { color: var(--text); margin-bottom: .5rem; }

.status-order-placed    { background: rgba(232,161,58,.18);  color: #F0B75E; }
.status-preparing       { background: rgba(76,141,232,.18);  color: #7DAcF2; }
.status-packed          { background: rgba(164,107,232,.18); color: #C09BF0; }
.status-out-for-delivery{ background: rgba(255,90,60,.18);   color: #FF8A6E; }
.status-delivered       { background: rgba(95,184,120,.18);  color: #7ED396; }

/* Stock row */
.stock-name { font-weight: 600; }
</style>
"""


# Original pizza-slice illustration (not a logo/character): a cheese slice with a
# browned crust, and toppings that VARY per pizza so each one looks different.
_SLICE_BASE = (
    "<path d='M13 23 Q32 12 51 23 L32 57 Z' fill='#F7C948'/>"
    "<path d='M13 23 Q32 12 51 23' stroke='#D9843A' stroke-width='6' stroke-linecap='round' fill='none'/>"
)

# name -> toppings as (cx, cy, r, color)
_TOPPINGS = {
    "margherita":     [(25, 31, 3.2, "#E2574C"), (39, 32, 3.2, "#E2574C"), (32, 43, 2.6, "#E2574C"), (43, 27, 2.0, "#5FB878"), (22, 39, 2.0, "#5FB878")],
    "four cheese":    [(25, 31, 3.4, "#FBE8B0"), (39, 31, 3.2, "#FBE8B0"), (32, 42, 3.0, "#FBE8B0"), (43, 27, 2.2, "#EBCB7A"), (22, 38, 2.0, "#EBCB7A")],
    "veggie supreme": [(25, 31, 3.0, "#4CAF50"), (39, 31, 3.0, "#E2574C"), (32, 43, 2.8, "#A06CD5"), (43, 26, 2.0, "#2E2A28"), (22, 38, 2.4, "#F2C94C")],
    "vegan garden":   [(25, 31, 3.0, "#5FB878"), (39, 32, 2.8, "#4CAF50"), (32, 42, 2.6, "#3E9B5A"), (43, 26, 2.0, "#8BC34A"), (22, 38, 2.0, "#5FB878")],
    "pepperoni":      [(25, 30, 3.4, "#CE3B2B"), (39, 31, 3.4, "#CE3B2B"), (32, 44, 3.0, "#CE3B2B"), (43, 26, 2.6, "#CE3B2B"), (22, 39, 2.6, "#CE3B2B")],
    "bbq chicken":    [(25, 31, 3.2, "#D8A566"), (39, 31, 3.2, "#D8A566"), (32, 43, 2.8, "#B5532E"), (43, 26, 2.0, "#5FB878"), (22, 38, 2.4, "#D8A566")],
}
_DIET_FALLBACK = {"veg": "margherita", "vegan": "vegan garden", "non-veg": "pepperoni"}


def _toppings(name, diet):
    key = (name or "").strip().lower()
    if key in _TOPPINGS:
        return _TOPPINGS[key]
    return _TOPPINGS[_DIET_FALLBACK.get(diet, "margherita")]


def pizza_svg(px=30, name="", diet="veg"):
    """Inline pizza slice sized for a menu card, with toppings for this pizza."""
    dots = "".join(f"<circle cx='{x}' cy='{y}' r='{r}' fill='{c}'/>" for x, y, r, c in _toppings(name, diet))
    return (
        f"<svg class='pizza-ico' width='{px}' height='{px}' viewBox='0 0 64 64' "
        "xmlns='http://www.w3.org/2000/svg' aria-hidden='true'>" + _SLICE_BASE + dots + "</svg>"
    )


# Banner uses a full-size pepperoni slice (CSS sizes it).
PIZZA = (
    "<svg viewBox='0 0 64 64' xmlns='http://www.w3.org/2000/svg' aria-hidden='true'>"
    + _SLICE_BASE
    + "".join(f"<circle cx='{x}' cy='{y}' r='{r}' fill='{c}'/>" for x, y, r, c in _TOPPINGS["pepperoni"])
    + "</svg>"
)


def inject(st):
    st.markdown(CSS, unsafe_allow_html=True)


def hero(st, title, subtitle):
    st.markdown(
        f"<div class='hero'><h1>{title}</h1><span class='sub'>{subtitle}</span></div>",
        unsafe_allow_html=True,
    )


def diet_badge(diet):
    cls = {"veg": "badge-veg", "vegan": "badge-vegan", "non-veg": "badge-nonveg"}.get(diet, "badge-veg")
    return f"<span class='badge {cls}'>{diet}</span>"


def stock_pill(n):
    n = int(n)
    if n == 0:
        return "<span class='pill pill-out'>sold out</span>"
    cls = "pill-low" if n <= 3 else "pill-ok"
    return f"<span class='pill {cls}'>{n} left</span>"


def status_pill(status):
    cls = "status-" + status.replace(" ", "-")
    return f"<span class='status {cls}'>{status}</span>"


def money(value):
    return f"{Decimal(value):.2f}"
