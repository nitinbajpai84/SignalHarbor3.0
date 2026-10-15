import { useSyncExternalStore, type ReactNode } from "react";
import { Link } from "react-router-dom";

// The Consume sub-bar: five tabs on the left, the currency switch at the top right. The currency is one choice for Today, Financial health and Markets,
// kept for the visit (sessionStorage), so moving between those pages does not reset it.
export type Tab = "today" | "health" | "markets" | "reports" | "whatif";
export const TABS: [Tab, string, string][] = [
  ["today", "Today", "/centre/consume"], ["health", "Financial health", "/centre/consume/health"], ["markets", "Markets", "/centre/consume/markets"],
  ["reports", "Reports", "/centre/consume/reports"], ["whatif", "What if", "/centre/consume/what-if"],
];
export const WITH_CURRENCY: Tab[] = ["today", "health", "markets"];

const KEY = "sh_consume_ccy";
let fallback = "USD"; // used when the browser blocks storage
const read = () => { try { return sessionStorage.getItem(KEY) === "SGD" ? "SGD" : "USD"; } catch { return fallback; } };
const listeners = new Set<() => void>();
const subscribe = (f: () => void) => { listeners.add(f); return () => { listeners.delete(f); }; };
export function useCurrency(): [string, (c: string) => void] {
  const ccy = useSyncExternalStore(subscribe, read);
  return [ccy, (c) => { fallback = c; try { sessionStorage.setItem(KEY, c); } catch { /* not kept */ } listeners.forEach((f) => f()); }];
}

/** A small two-or-three way switch drawn as one pill (the artboards' currency and period switch). */
export function Segmented<T extends string>({ label, value, options, onChange }: { label: string; value: T; options: [T, string][]; onChange: (v: T) => void }) {
  return (
    <div role="group" aria-label={label} style={{ display: "flex", background: "var(--ds-surface)", border: "1px solid var(--ds-line)", borderRadius: 999, padding: 3 }}>
      {options.map(([v, text]) => (
        <button key={v} type="button" aria-pressed={v === value} onClick={() => onChange(v)}
          style={{ background: v === value ? "var(--ds-teal)" : "transparent", color: v === value ? "var(--ds-on-teal)" : "var(--ds-ink-soft)", border: 0, borderRadius: 999,
            padding: "6px 14px", fontSize: 13, fontWeight: v === value ? 600 : 500, cursor: "pointer", fontFamily: "inherit" }}>{text}</button>
      ))}
    </div>
  );
}

export default function ConsumeBar({ here, extra }: { here: Tab; extra?: ReactNode }) {
  const [ccy, setCcy] = useCurrency();
  return (
    <nav aria-label="Consume tabs" className="ds-subbar" style={{ alignItems: "center" }}>
      {TABS.map(([id, label, to]) => <Link key={id} to={to} aria-current={id === here ? "page" : undefined}>{label}</Link>)}
      <span style={{ marginLeft: "auto", display: "flex", gap: 12, alignItems: "center", padding: "6px 0" }}>
        {extra}
        {WITH_CURRENCY.includes(here) ? <Segmented label="Currency" value={ccy} options={[["USD", "USD"], ["SGD", "SGD"]]} onChange={setCcy} /> : null}
      </span>
    </nav>
  );
}
