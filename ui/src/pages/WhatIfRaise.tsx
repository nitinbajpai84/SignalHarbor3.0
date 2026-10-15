import { useEffect, useState, type CSSProperties, type FormEvent } from "react";

import { Button } from "../design";
import { apiGet, apiSend } from "../api/client";
import { LENS_NAMES, type LensList } from "./consumeLens";

// "Turn this into an opportunity" (spec 60 Screen D): the kept what-if prefills a hypothesis; the person edits and raises it.

export interface RaiseMoved { code: string; label: string; change_pct: number; latest: { period: string; value: number; moved_value: number } | null }
const FIELD: CSSProperties = { minHeight: 44, padding: "8px 12px", borderRadius: 8, border: "1px solid var(--ds-line-2)", background: "var(--ds-ground)", color: "var(--ds-ink)", font: "inherit", fontSize: 13, boxSizing: "border-box", width: "100%" };
const LABEL: CSSProperties = { display: "flex", flexDirection: "column", gap: 4, fontSize: 13 };
const num = (n: number) => Number(n.toFixed(2));

export function RaiseFromWhatIf({ driver, pct, moved, basis, onClose, onRaised }: {
  driver: string; pct: number; moved: RaiseMoved[]; basis: string; onClose: () => void; onRaised: (id: string) => void;
}) {
  const first = moved.find((m) => m.latest) ?? moved[0]!;
  const [belief, setBelief] = useState(() => `If ${driver} moves ${pct}%, ${first.label}${first.latest ? ` moves from ${num(first.latest.value)} to ${num(first.latest.moved_value)}` : " moves"}`);
  const [lens, setLens] = useState("");
  const [lenses, setLenses] = useState<LensList["lenses"]>([]);
  const [target, setTarget] = useState("");
  const [err, setErr] = useState<string | null>(null), [busy, setBusy] = useState(false);
  useEffect(() => {
    let live = true;
    apiGet<LensList>("/api/company/consume/lenses").then((d) => {
      if (!live) return;
      setLenses(d.lenses);
      setLens(moved.map((m) => d.lenses.find((l) => l.measures?.includes(m.code))?.key).find(Boolean) ?? "");  // the first moved measure that sits in a view
    }).catch(() => undefined);
    return () => { live = false; };
  }, [moved]);

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!belief.trim() || !lens) return;
    setBusy(true);
    const baseline = first.latest ? { value: first.latest.value, period: first.latest.period } : null;
    apiSend<{ id: string }>("POST", "/api/company/whatif/keep", { driver, change_pct: pct, note: belief })
      .then((kept) => apiSend<{ id: string }>("POST", "/api/intents/opportunities", {
        title: belief.slice(0, 120), noticed: belief, touches: { measures: moved.map((m) => m.code) },
        evidence: { text: basis, kind: "whatif", source: { kind: "whatif", ref: kept.id } },
      }))
      .then((o) => apiSend("POST", `/api/intents/opportunities/${encodeURIComponent(o.id)}/hypothesis`, { lens, belief, baseline, target: target.trim() || null }).then(() => onRaised(o.id)))
      .catch(() => { setErr("That was not raised. Please try again."); setBusy(false); });
  };
  return (
    <div role="dialog" aria-label="Turn this into an opportunity" className="ds-card ds-side" style={{ position: "fixed", inset: "10% auto auto 50%", transform: "translateX(-50%)", width: "min(520px, 94vw)", maxHeight: "80vh", overflow: "auto", zIndex: 40 }}>
      <h2 style={{ margin: 0 }}>Turn this into an opportunity</h2>
      <form onSubmit={submit} style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        <label style={LABEL}>What you believe<textarea style={FIELD} rows={3} value={belief} onChange={(e) => setBelief(e.target.value)} /></label>
        <label style={LABEL}>Business view
          <select style={FIELD} value={lens} onChange={(e) => setLens(e.target.value)}>
            <option value="">Pick a business view</option>
            {Object.entries(LENS_NAMES).map(([k, n]) => <option key={k} value={k}>{lenses.find((l) => l.key === k)?.name ?? n}</option>)}
          </select>
        </label>
        <p className="ds-muted">Evidence: {basis}</p>
        <p className="ds-muted">Baseline: {first.latest ? `${num(first.latest.value)} (${first.latest.period})` : "Not available yet: the measure has no value"}</p>
        <label style={LABEL}>Target (optional)
          <input style={FIELD} value={target} onChange={(e) => setTarget(e.target.value)} />
          <span className="ds-muted">The what-if is a straight-line estimate, not a target.</span>
        </label>
        {err ? <p role="alert" className="ds-warn">{err}</p> : null}
        <div style={{ display: "flex", gap: 8 }}>
          <Button variant="primary" type="submit" disabled={busy || !belief.trim() || !lens}>Raise it</Button>
          <Button onClick={onClose}>Cancel</Button>
        </div>
      </form>
    </div>
  );
}
