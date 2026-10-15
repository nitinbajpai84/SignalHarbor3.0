import { Fragment, useEffect, useRef, useState } from "react";

import { ApiError } from "../../api/client";
import { Button, Pill } from "../../design";
import { getSop, sopHref, type Sop } from "./api";

// K7: on a signed intent of work, "Download the procedure" and a preview of the procedure written from the process map.
export default function SopPanel({ iid }: { iid: string }) {
  const [sop, setSop] = useState<Sop | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const top = useRef<HTMLElement>(null);
  // UC9-01: the procedure opens inside the conversation panel, often below its fold: bring its heading into view
  useEffect(() => { if (sop) top.current?.scrollIntoView?.({ behavior: "smooth", block: "start" }); }, [sop]);
  const show = async () => {
    setBusy(true);
    try { setSop(await getSop(iid)); setError(""); }
    catch (err) { setError(err instanceof ApiError && err.message ? err.message : "The procedure could not be shown. Please try again."); }
    finally { setBusy(false); }
  };
  return (
    <div style={{ display: "grid", gap: 8 }}>
      <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
        <a className="ds-btn ds-btn--primary" href={sopHref(iid)} download>Download the procedure</a>
        <Button variant="secondary" disabled={busy} onClick={() => (sop ? setSop(null) : void show())}>{sop ? "Hide the procedure" : "Read the procedure here"}</Button>
        <span className="ds-muted">A step-by-step procedure written from the signed process map.</span>
      </div>
      {error ? <p role="alert">{error}</p> : null}
      {sop ? (
        <section aria-label="Procedure preview" ref={top} tabIndex={-1}>
          <h3 style={{ margin: "0 0 4px" }}>{sop.title}</h3>
          <p className="ds-muted" style={{ margin: "0 0 8px" }}>Version {sop.version}. {sop.signed}</p>
          <p style={{ margin: "0 0 8px" }}><strong>Purpose.</strong> {sop.purpose}</p>
          <p style={{ margin: "0 0 8px" }}><strong>Scope.</strong> {sop.scope}</p>
          <p style={{ margin: "0 0 8px" }}><strong>Roles.</strong> {sop.roles.join(", ") || "Not stated yet"}</p>
          <p style={{ margin: "0 0 8px" }}><strong>Systems.</strong> {sop.systems.join(", ") || "Not stated yet"}</p>
          <ol style={{ margin: "0 0 8px", paddingLeft: 20 }}>
            {sop.steps.map((s) => (
              <li key={s.n}>
                <strong>{s.name}</strong> {s.manual ? <Pill tone="late">Manual: could be automated</Pill> : null}
                <dl className="ds-muted" style={{ display: "grid", gridTemplateColumns: "max-content 1fr", gap: "0 12px", margin: "2px 0" }}>
                  {([["Who", s.who], ["System", s.system], ["Input", s.input], ["Output", s.output], ["Control", s.control], ["If it goes wrong", s.exception]] as const).map(([k, v]) => (
                    <Fragment key={k}><dt>{k}</dt><dd style={{ margin: 0 }}>{v}</dd></Fragment>
                  ))}
                </dl>
                {s.handovers.map((h, i) => <div key={i} className="ds-muted">Hand over to step {h.to_step}: {h.what}</div>)}
                {/* a9.5: every step says where it came from: the signed process map and the person's own words, never an agent's guess */}
                <details className="ds-muted">
                  <summary className="ds-link" style={{ cursor: "pointer" }}>Where is this from?</summary>
                  Step {s.n} of the process map in this intent of work. {sop.signed} The control and what to do when it goes wrong are written as
                  the team stated them; where nothing was stated the procedure says so.
                </details>
              </li>
            ))}
          </ol>
          {/* UC9-05: the same sections as the downloaded file, after the steps */}
          {([["Manual steps flagged for automation", sop.steps.filter((s) => s.manual).map((s) => `${s.n}. ${s.name}`)],
             ["Controls", sop.controls], ["Definitions", sop.definitions], ["Open points", sop.open_points]] as const).map(([head, lines]) => (
            <div key={head} style={{ margin: "0 0 8px" }}>
              <strong>{head}</strong>
              {lines.length ? <ul style={{ margin: 0, paddingLeft: 20 }}>{lines.map((x) => <li key={x}>{x}</li>)}</ul> : <p style={{ margin: 0 }}>None</p>}
            </div>
          ))}
        </section>
      ) : null}
    </div>
  );
}
