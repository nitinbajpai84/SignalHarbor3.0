import type { ReuseOffer as Offer } from "../api";

/** Decision 1: a verified figure already exists. The person picks per figure; the choice is sent in the `reuse` map on confirm. */
export default function ReuseOffer({ offers, value, onChange }: { offers: Offer[]; value: Record<string, string | null>; onChange: (v: Record<string, string | null>) => void }) {
  if (!offers.length) return null;
  const set = (id: string, to: string | null) => onChange({ ...value, [id]: to });
  return (
    <section className="v3-bgroup" aria-label="Figures you already have">
      <h3>Figures you already have</h3>
      {offers.map((o) => {
        const using = value[o.figure_id] === o.figure_id;
        const own = o.figure_id in value && value[o.figure_id] === null;
        return (
          <div key={o.figure_id} className="v3-row" style={{ alignItems: "center", flexWrap: "wrap" }}>
            <span>Use {o.name} (verified, run {o.verified_runs} {o.verified_runs === 1 ? "time" : "times"}, first used by {o.first_used_by})?</span>
            <button type="button" className="go" aria-pressed={using} onClick={() => set(o.figure_id, o.figure_id)}>Use</button>
            <button type="button" aria-pressed={own} onClick={() => set(o.figure_id, null)}>Keep my own</button>
          </div>
        );
      })}
    </section>
  );
}
