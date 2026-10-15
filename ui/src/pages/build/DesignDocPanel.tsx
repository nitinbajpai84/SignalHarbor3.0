import { useRef, useState } from "react";

import { Button, EmptyState, Pill } from "../../design";
import { useLoad } from "../BuildCentre";
import { day } from "../BuildCentre";
import "./chain.css";
import { designDownload, designPath, redraft, specDownload, uploadSpec, type DesignDoc, type SpecKind } from "./spanApi";
import { line, SECTIONS, sc } from "./spanCopy";
import { SpanGate, sayWhy } from "./SpanModelPanel";

const KINDS: SpecKind[] = ["current", "target", "delta"];
/** The diagram sits in a frame with no permissions at all: no script, no forms, nothing from outside. */
const frame = (svg: string) => `<!doctype html><meta charset="utf-8"><body style="margin:0;background:#fff">${svg}`;

/** Room 1: the design document Span drafts from the records. Everyone reads it; the architect may download and upload the spec and ask for a redraft. */
export default function DesignDocPanel() {
  const { data, state, retry, setData } = useLoad<DesignDoc>(designPath);
  const [kind, setKind] = useState<SpecKind>("target");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const pick = useRef<HTMLInputElement>(null);
  const doc = data?.doc ?? null;
  const svg = data?.diagrams?.[kind];
  const upload = (file: File | undefined) => {
    if (!file) return;
    file.text().then((t) => uploadSpec(kind, JSON.parse(t) as unknown))
      .then(() => { setErr(""); setMsg(sc.uploadedSpec); retry(); })
      .catch((e: unknown) => { setMsg(""); setErr(e instanceof SyntaxError ? sc.specBad : sayWhy(e)); });
    if (pick.current) pick.current.value = "";
  };
  const again = () => {
    redraft().then((r) => { setErr(""); setMsg(r.message || sc.redrafting); }).catch((e: unknown) => { setMsg(""); setErr(sayWhy(e)); });
  };
  const signed = doc?.state === "signed";
  const by = doc?.signed_by?.[0];
  return (
    <section id="design" aria-label="Design document">
      <SpanGate state={state} retry={retry} title={sc.designTitle}>
        <p className="bc-note">{sc.designLine}</p>
        {!doc ? <EmptyState title={data?.empty || sc.designEmpty} lines={[]} /> : (
          <>
            <p>
              <Pill tone={signed ? "signed" : "draft"}>{signed && by ? sc.signedBanner(by.name, day(by.at)) : sc.draftBanner}</Pill>
              {!signed ? <> <Pill tone="draft">{sc.tag}</Pill></> : null}
            </p>
            {data?.fallback ? <p role="status" className="ds-warn">{data.message || sc.fallback}</p> : null}
            <div className="bc-actions" role="group" aria-label={sc.diagramOf}>
              {KINDS.map((k) => <button key={k} type="button" className={`ds-chip${k === kind ? " ds-chip--active" : ""}`} aria-pressed={k === kind} onClick={() => setKind(k)}>{sc.tabs[k]}</button>)}
            </div>
            {svg ? <iframe title={`${sc.diagramOf}: ${sc.tabs[kind]}`} sandbox="" srcDoc={frame(svg)} style={{ width: "100%", height: 360, border: "1px solid var(--ds-line)", borderRadius: "var(--ds-radius)", background: "#fff" }} />
              : <p role="status" className="ds-warn">{data?.diagram_errors?.[0] ?? sc.diagramMissing}</p>}
            {SECTIONS.map(([id, title]) => {
              const lines = doc.sections[id] ?? [];
              return lines.length ? (
                <details key={id} className="ds-card bc-sec" open={id === "purpose"}>
                  <summary>{title}</summary>
                  <ul className="bc-lines">
                    {lines.map((l, i) => (
                      <li key={i}>{line(l.text)} <span className="ds-muted">{l.mark === "stated" ? sc.statedTag : sc.tag}</span></li>
                    ))}
                  </ul>
                </details>
              ) : null;
            })}
            <div className="bc-actions">
              <a className="ds-btn ds-btn--primary" href={designDownload} download>{sc.download}</a>
              {data?.can_edit ? (
                <>
                  <a className="ds-btn" href={specDownload(kind)} download={`${kind}-spec.json`}>{sc.downloadSpec}</a>
                  <Button onClick={() => pick.current?.click()}>{sc.uploadSpec}</Button>
                  <input ref={pick} type="file" accept="application/json,.json" hidden aria-label={sc.uploadSpec} onChange={(e) => upload(e.target.files?.[0])} />
                  <Button onClick={again}>{sc.redraft}</Button>
                </>
              ) : null}
            </div>
          </>
        )}
        {msg ? <p role="status" className="bc-note">{msg}</p> : null}
        {err ? <p role="alert" className="ds-warn">{err}</p> : null}
      </SpanGate>
    </section>
  );
}
