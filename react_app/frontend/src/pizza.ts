// Original pizza-slice SVG whose toppings vary per pizza (shared idea with the
// Streamlit theme). Returns an inline SVG string.
const BASE =
  "<path d='M13 23 Q32 12 51 23 L32 57 Z' fill='#F7C948'/>" +
  "<path d='M13 23 Q32 12 51 23' stroke='#D9843A' stroke-width='6' stroke-linecap='round' fill='none'/>";

type Dot = [number, number, number, string];

const TOPS: Record<string, Dot[]> = {
  margherita: [[25, 31, 3.2, "#E2574C"], [39, 32, 3.2, "#E2574C"], [32, 43, 2.6, "#E2574C"], [43, 27, 2, "#5FB878"], [22, 39, 2, "#5FB878"]],
  "four cheese": [[25, 31, 3.4, "#FBE8B0"], [39, 31, 3.2, "#FBE8B0"], [32, 42, 3, "#FBE8B0"], [43, 27, 2.2, "#EBCB7A"], [22, 38, 2, "#EBCB7A"]],
  "veggie supreme": [[25, 31, 3, "#4CAF50"], [39, 31, 3, "#E2574C"], [32, 43, 2.8, "#A06CD5"], [43, 26, 2, "#2E2A28"], [22, 38, 2.4, "#F2C94C"]],
  "vegan garden": [[25, 31, 3, "#5FB878"], [39, 32, 2.8, "#4CAF50"], [32, 42, 2.6, "#3E9B5A"], [43, 26, 2, "#8BC34A"], [22, 38, 2, "#5FB878"]],
  pepperoni: [[25, 30, 3.4, "#CE3B2B"], [39, 31, 3.4, "#CE3B2B"], [32, 44, 3, "#CE3B2B"], [43, 26, 2.6, "#CE3B2B"], [22, 39, 2.6, "#CE3B2B"]],
  "bbq chicken": [[25, 31, 3.2, "#D8A566"], [39, 31, 3.2, "#D8A566"], [32, 43, 2.8, "#B5532E"], [43, 26, 2, "#5FB878"], [22, 38, 2.4, "#D8A566"]],
};

const DIET_FALLBACK: Record<string, string> = {
  veg: "margherita",
  vegan: "vegan garden",
  "non-veg": "pepperoni",
};

export function pizzaSvg(name: string, diet: string): string {
  const tops = TOPS[name.toLowerCase()] ?? TOPS[DIET_FALLBACK[diet] ?? "margherita"];
  const dots = tops.map(([x, y, r, c]) => `<circle cx='${x}' cy='${y}' r='${r}' fill='${c}'/>`).join("");
  return `<svg viewBox='0 0 64 64' xmlns='http://www.w3.org/2000/svg' aria-hidden='true'>${BASE}${dots}</svg>`;
}
