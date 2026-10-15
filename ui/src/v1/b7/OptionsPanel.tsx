import { useEffect, useState } from "react";

import { ApiError } from "../../api/client";
import { Button } from "../../design";
import { patchTile, tileOptions, type Option } from "./panelsApi";

// STUDIO2 F2 (design board 2): three ways to show the selected chart; Lumen's pick is marked. "Use this" applies the option's patch.
const plain = (e: unknown, fallback: string) => (e instanceof ApiError && e.message ? e.message : fallback);
export default function OptionsPanel({ pid, did, tid, onChanged }: { pid: string; did: string; tid: string; onChanged: () => void }) {
  const [options, setOptions] = useState<Option[] | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let live = true;
    setOptions(null); setError("");
    tileOptions(pid, did, tid).then((r) => { if (live) setOptions(r.options); })
      .catch((e: unknown) => { if (live) { setOptions([]); setError(plain(e, "Lumen could not offer options just now. Please try again.")); } });
    return () => { live = false; };
  }, [pid, did, tid]);
  const use = async (o: Option) => {
    setError("");
    try { await patchTile(pid, did, tid, o.patch); onChanged(); } catch (e) { setError(plain(e, "That did not go through. Please try again.")); }
  };
  return (
    <section aria-label="Three ways to show it">
      <h3 className="ds-serif" style={{ margin: "0 0 8px" }}>Three ways to show it. Pick one, then keep talking.</h3>
      {options === null ? <p className="ds-muted" role="status">Lumen is working out the options.</p> : null}
      {error ? <p role="alert">{error}</p> : null}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 12 }}>
        {(options ?? []).map((o) => (
          <article key={o.label} data-pick={o.pick} className="ds-card" style={{ padding: 14, border: o.pick ? "2px solid #5FC2C2" : "1px solid #22344D", borderRadius: 14 }}>
            <div style={{ fontWeight: 600 }}>{o.label}</div>
            <p className="ds-muted" style={{ fontSize: 13 }}>{o.why}{o.pick ? " Lumen's pick." : ""}</p>
            {o.book ? <p style={{ fontSize: 13, margin: "4px 0" }}>Industry practice Lumen suggests: “{o.book.line}” <span className="ds-muted">{o.book.used}</span></p> : null}
            <Button variant={o.pick ? "primary" : undefined} aria-label={`Use this: ${o.label}`} onClick={() => void use(o)}>Use this</Button>
          </article>))}
      </div>
    </section>
  );
}
