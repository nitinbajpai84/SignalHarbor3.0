import { useEffect, useState } from "react";

import { Button, day } from "../../design";
import { getIndexMap, signIndexMap, type IndexMap } from "./api";
import { plain } from "./format";

// V6: which index each fund is compared with is a signed record, not a guess from the fund's name. Everyone reads who signed and when;
// only the head of data signs (the server checks the seat again). A fund with no signed index shows "No index is signed for this fund yet."
export default function IndexMapPanel({ onSigned }: { onSigned?: () => void }) {
  const [m, setM] = useState<IndexMap | null>(null);
  const [pick, setPick] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    let live = true;
    getIndexMap().then((r) => { if (live) { setM(r); setPick(Object.fromEntries(r.funds.map((f) => [f.fund_id, f.series_key ?? f.proposed_series_key ?? ""]))); } }, () => undefined);
    return () => { live = false; };
  }, []);
  if (!m || (!m.signed && !m.can_sign && m.funds.length === 0)) return null;
  async function sign() {
    setBusy(true); setError("");
    try {
      const r = await signIndexMap(Object.fromEntries(Object.entries(pick).filter(([, v]) => v)));
      setM(r); onSigned?.();
    } catch (e) { setError(plain(e)); } finally { setBusy(false); }
  }
  return (
    <section aria-label="Which index each fund is compared with" className="ds-card" style={{ padding: 16, margin: "12px 0" }}>
      <h3 style={{ marginTop: 0 }}>Which index each fund is compared with</h3>
      <p className="ds-muted" style={{ margin: "0 0 8px" }}>
        {m.signed ? `Signed by ${m.signed_by ?? "the head of data"}${m.signed_at ? ` on ${day(m.signed_at)}` : ""}, version ${m.version}.` : "Not signed yet. No fund is compared with an index until the head of data signs which one fits."}
      </p>
      {m.can_sign ? (
        <>
          <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "grid", gap: 6 }}>
            {m.funds.map((f) => (
              <li key={f.fund_id} style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
                <label style={{ display: "flex", gap: 8, alignItems: "center" }}><span style={{ minWidth: 220 }}>{f.fund}</span>
                  <select className="ds-input" aria-label={`Index for ${f.fund}`} value={pick[f.fund_id] ?? ""} onChange={(e) => setPick({ ...pick, [f.fund_id]: e.target.value })} style={{ width: "auto" }}>
                    <option value="">No index</option>
                    {m.choices.map((c) => <option key={c.series_key} value={c.series_key}>{c.name}</option>)}
                  </select></label>
                {!f.series_key && f.proposed_series_key ? <span className="ds-muted">proposed</span> : null}
              </li>))}
          </ul>
          {error ? <p role="alert">{error}</p> : null}
          <p style={{ marginBottom: 0 }}><Button variant="primary" disabled={busy} onClick={() => void sign()}>Sign the mapping</Button></p>
        </>
      ) : m.signed ? (
        <ul style={{ margin: 0, paddingLeft: 18 }}>{m.funds.filter((f) => f.series_key).map((f) => <li key={f.fund_id}>{f.fund}: {m.choices.find((c) => c.series_key === f.series_key)?.name ?? f.series_key}</li>)}</ul>
      ) : null}
    </section>
  );
}
