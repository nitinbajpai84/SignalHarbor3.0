import { useState, type ReactNode } from "react";
import { Link } from "react-router-dom";

import DownloadButton from "../../../components/DownloadButton";
import Panel from "../../../components/Panel";
import StatusPill from "../../../components/StatusPill";
import { bringBack, catalogueExportUrl, leaveOut, signedBundleUrl, type Gate, type GateMeasure, type SignoffView } from "../api";
import { m2Signoff as T } from "../copy";
import { glossaryExcelUrl, glossaryPrintUrl } from "../glossary/glossaryApi";

const day = (iso: string) => new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" });
type Run = (work: () => Promise<SignoffView>, done?: string) => Promise<void>;

/** M2-E4: one line of the checklist: what it asks, whether it is done, what is open, and where it is fixed. */
function Line({ label, ok, reasons, to }: { label: string; ok: boolean; reasons: string[]; to: string | null }) {
  const G = T.gate;
  return (
    <li>
      <strong>{label}</strong> <StatusPill tone={ok ? "success" : "warning"}>{ok ? G.done : G.openPill}</StatusPill>
      {!ok && to ? <> <Link to={to}>{G.fix}</Link></> : null}
      {reasons.length ? <ul className="n-e1-def-note">{reasons.map((r) => <li key={r}>{r}</li>)}</ul> : null}
    </li>
  );
}

function LeaveOut({ m, baselineId, busy, run }: { m: GateMeasure; baselineId: string; busy: boolean; run: Run }) {
  const [why, setWhy] = useState("");
  return (
    <span style={{ display: "inline-flex", gap: 6 }}>
      <input type="text" aria-label={T.gate.leftOut.reason(m.name)} value={why} onChange={(e) => setWhy(e.target.value)} />
      <button type="button" className="n-btn" disabled={busy || !why.trim()} aria-label={`${T.gate.leftOut.button}: ${m.name}`} onClick={() => void run(() => leaveOut(baselineId, m.kpi_id, why.trim()))}>
        {T.gate.leftOut.button}
      </button>
    </span>
  );
}

/** The ready-to-build checklist (the same verdict for everyone; the reasons are about what this person may see) and the measures left out. */
export function GatePanel({ gate, baselineId, open, canLeave, busy, run }: { gate: Gate; baselineId: string; open: boolean; canLeave: boolean; busy: boolean; run: Run }) {
  const G = T.gate;
  const to = (k: keyof Gate["fix"]) => `/modules/m2_baseline/${gate.fix[k]}/${baselineId}`;
  const notReady = gate.measures.items.filter((i) => !i.ready);
  return (
    <Panel title={G.title} actions={<StatusPill tone={gate.ok ? "success" : "warning"}>{gate.ok ? G.ready : G.notReady}</StatusPill>}>
      <p className="n-e1-def-note">{G.help}</p>
      <ul className="n-companion-checklist static" aria-label={G.title}>
        <Line label={G.measures(gate.measures.ready, gate.measures.total)} ok={gate.measures.ready === gate.measures.total && gate.measures.total > 0} reasons={[]} to={to("measures")} />
        <Line label={G.glossary} ok={gate.glossary.ok} reasons={gate.glossary.reasons} to={to("glossary")} />
        <Line label={G.governance} ok={gate.governance.ok} reasons={gate.governance.reasons} to={to("governance")} />
        <Line label={G.open(gate.open.n)} ok={gate.open.n === 0} reasons={[]} to={to("open")} />
      </ul>
      {gate.restricted ? <p role="note" className="n-e1-def-note">{G.restricted}</p> : null}
      {notReady.length ? (
        <ul aria-label={G.measures(gate.measures.ready, gate.measures.total)}>
          {notReady.map((m) => (
            <li key={m.kpi_id}>
              <span className="n-e1-def-name">{m.name}</span>
              <ul className="n-e1-def-note">{m.reasons.map((r) => <li key={r}>{r}</li>)}</ul>
              {open && canLeave ? <LeaveOut m={m} baselineId={baselineId} busy={busy} run={run} /> : null}
            </li>
          ))}
        </ul>
      ) : null}
      <h3 className="n-e1-def-name">{G.leftOut.title}</h3>
      {gate.left_out.length === 0 ? <p className="n-e1-def-note">{G.leftOut.none}</p> : (
        <ul>
          {gate.left_out.map((r) => (
            <li key={r.kpi_id}>
              {G.leftOut.line(r.name, r.reason, r.by)}{" "}
              {open && canLeave ? (
                <button type="button" className="n-btn sm" disabled={busy} aria-label={`${G.leftOut.bring}: ${r.name}`} onClick={() => void run(() => bringBack(baselineId, r.kpi_id))}>
                  {G.leftOut.bring}
                </button>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}

/** The two documents the signature covers, each with its downloads, then the one bundle. Once signed: "Signed: ready to build", the signers and the fingerprints. */
export function DocumentsPanel({ view, baselineId }: { view: SignoffView; baselineId: string }) {
  const D = T.documents;
  const signed = view.status === "signed";
  const fp = (id: string) => view.documents?.find((d) => d.id === id);
  const Doc = ({ id, name, note, children }: { id: string; name: string; note?: string; children: ReactNode }) => {
    const d = fp(id);
    return (
      <div className="n-e1-signature" style={{ display: "grid", gap: 6 }}>
        <div className="n-e1-def-name">{name}</div>
        {note ? <div className="n-e1-def-note">{note}</div> : null}
        {d?.sha256 ? <div className="n-e1-def-note">{D.fingerprint(d.sha256)} {d.unchanged === false ? <strong role="alert">{D.changed}</strong> : <span>{D.same}</span>}</div> : null}
        <div className="n-flex wrap">{children}</div>
      </div>
    );
  };
  return (
    <Panel title={D.title} actions={<StatusPill tone={signed ? "success" : "muted"}>{signed ? D.signed : D.draft}</StatusPill>}>
      <p className="n-e1-def-note">{D.intro}</p>
      {signed ? (
        <ul>
          {view.signatures.map((s) => <li key={s.slot}>{D.signedBy(s.name, s.label, day(s.at))}</li>)}
        </ul>
      ) : null}
      <div className="n-e1-charter-grid">
        <Doc id="business_glossary" name={D.glossary}>
          <DownloadButton path={glossaryExcelUrl(baselineId)} fallbackName="glossary.xlsx" label={`${D.glossary}: ${D.excel}`} />
          <DownloadButton path={glossaryPrintUrl(baselineId)} fallbackName="glossary.html" label={`${D.glossary}: ${D.print}`} />
        </Doc>
        <Doc id="data_catalogue" name={D.catalogue} note={D.catalogueNote}>
          <DownloadButton path={catalogueExportUrl(baselineId)} fallbackName="data-catalogue.xlsx" label={`${D.catalogue}: ${D.excel}`} />
        </Doc>
      </div>
      <p>
        <DownloadButton primary path={signedBundleUrl(baselineId)} fallbackName={signed ? "signed-baseline.zip" : "draft-baseline.zip"} label={signed ? D.bundle : D.bundleDraft} />
      </p>
    </Panel>
  );
}
