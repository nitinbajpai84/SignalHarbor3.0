import type { Item, ItemKind } from "./api";

const LAYER: Partial<Record<ItemKind, string>> = { gold: "gold", silver: "silver", bronze: "bronze", assumption: "assumed", kpi: "kpi" };

/** The words on a box: a rule or an assumption is led by what it is, the rest by their own name. */
export const chipText = (i: Item): { lead: string; rest: string } =>
  i.kind === "rule" || i.kind === "brule" ? { lead: "Rule", rest: i.label } : i.kind === "assumption" ? { lead: "Assumed", rest: i.label }
    : i.kind === "signal" ? { lead: "Signal", rest: i.sub } : { lead: i.label, rest: i.sub };

export const Dot = ({ n }: { n: number }) => (n > 0 ? <span className="ks-dot" role="img" aria-label="Shared with other use cases" title="Shared with other use cases">{"●"}</span> : null);

/** One clickable box of the story. A gold dot means another use case also uses it. */
export default function Chip({ item, on, dim, onPick }: { item: Item; on: boolean; dim: boolean; onPick: (id: string) => void }) {
  const t = chipText(item);
  const cls = ["ks-chip", LAYER[item.kind] ?? "plain", on ? "on" : "", dim ? "dim" : ""].filter(Boolean).join(" ");
  return (
    <button type="button" className={cls} aria-pressed={on} onClick={() => onPick(item.id)}>
      <b>{t.lead}</b>{t.rest ? <> {"·"} {t.rest}</> : null}<Dot n={item.shared.length} />
    </button>
  );
}
