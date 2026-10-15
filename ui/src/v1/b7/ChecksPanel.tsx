import { useCallback, useEffect, useState } from "react";

import { ApiError } from "../../api/client";
import { Button } from "../../design";
import { getChecks, patchTile, type Check } from "./panelsApi";

// STUDIO2 F2 (design board 2): "Before it goes for approval, Lumen checks the charts". A fix applies the check's patch to the widget's tile.
const LEAD: Record<Check["kind"], string> = { counted_twice: "Counted twice.", flattened_trend: "Trend flattened.", space: "Space.", house_style: "House style.", too_many: "Too many." };
const plain = (e: unknown, fallback: string) => (e instanceof ApiError && e.message ? e.message : fallback);
export default function ChecksPanel({ pid, did, onChanged }: { pid: string; did: string; onChanged: () => void }) {
  const [checks, setChecks] = useState<Check[] | null>(null);
  const [error, setError] = useState("");
  const load = useCallback(() => getChecks(pid, did).then((r) => setChecks(r.checks))
    .catch((e: unknown) => { setChecks((c) => c ?? []); setError(plain(e, "The checks could not run just now. Please try again.")); }), [pid, did]);
  useEffect(() => { void load(); }, [load]);
  const fix = async (c: Check) => {
    setError("");
    try { await patchTile(pid, did, c.widget, c.fix!.patch); onChanged(); await load(); } catch (e) { setError(plain(e, "That did not go through. Please try again.")); }
  };
  return (
    <section aria-label="Lumen checks the charts">
      <h3 style={{ margin: "0 0 8px" }}>Before it goes for approval, Lumen checks the charts</h3>
      {checks === null ? <p className="ds-muted" role="status">Checking the charts.</p> : null}
      {checks?.length === 0 && !error ? <p className="ds-muted">Nothing to fix.</p> : null}
      {error ? <p role="alert">{error}</p> : null}
      <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: 8 }}>
        {(checks ?? []).map((c) => (
          <li key={c.id} style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "center" }}>
            <span><strong>{LEAD[c.kind]}</strong> {c.message}</span>
            {c.fix ? <Button variant="primary" onClick={() => void fix(c)}>{c.fix.label}</Button> : <span className="ds-muted">Applied</span>}
          </li>))}
      </ul>
    </section>
  );
}
