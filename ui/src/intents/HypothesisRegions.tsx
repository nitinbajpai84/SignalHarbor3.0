import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { ApiError, apiGet, apiSend } from "../api/client";
import { Button, Chip } from "../design";
import { BASIS, CONFIDENCE, H, LENSES, notYet } from "./radarCopy";

// Spec 57 Screen C: the four regions the 56 drawer gains between "North's judgement" and "Proposed start answers".
// Mount: <HypothesisRegions oppId hypothesisRef canEdit rejected onChanged /> (one line in OpportunityDrawer, see the report).
interface Trace { kind: string; ref: string; at: string }
interface Val { value: number | string; unit: string; periods?: string[]; trace?: Trace; by?: string; set_by?: string | null; per?: string; basis?: string }
interface Line { id: string; record_kind: "data" | "document" | "voice"; stance: "supports" | "counters"; text: string | null; trace: Trace | null; by: string | null; at?: string; anonymous?: boolean; restricted?: boolean; href?: string | null }
interface Version {
  v: number; at: string; by: string | null; belief: string; lens: string; measure: { id: string; name: string | null } | null;
  baseline: Val | null; target: Val | null; expected_uplift: Val | null; confidence: string | null; review_date: string | null; evidence: Line[];
  counter_check: { looked_for: string[]; found: string[]; verdict: "holds" | "broken"; why: string; broke_by?: { kind: string; ref: string }[] } | null;
  theme: { voices: number; by_source: Record<string, number> } | null;
  baseline_missing?: string | null; target_missing?: string | null; uplift_missing?: string | null;
}
interface Hypothesis { id: string; state: string; versions: Version[]; voices_named?: string[] }

const DATE = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short" });
const when = (iso: string) => { const d = new Date(iso); return Number.isNaN(d.getTime()) ? iso : DATE.format(d); };
const val = (v: Val | null, missing?: string | null, tail = "") => (v ? `${v.value} ${v.unit}${v.periods?.length ? ` (${v.periods.join(", ")})` : ""}${tail}` : notYet(missing));
const SOURCE_NAME: Record<string, string> = { wall: "Wall", checkin: "Check-in", brainstorm: "Brainstorm", backlog: "Backlog" };
const wide = () => typeof window === "undefined" || !window.matchMedia || window.matchMedia("(min-width: 700px)").matches;

function Region({ title, open, children }: { title: string; open?: boolean; children: React.ReactNode }) {
  return wide()
    ? <section aria-label={title}><h3>{title}</h3>{children}</section>
    : <details open={open} aria-label={title}><summary><strong>{title}</strong></summary>{children}</details>;
}

export function HypothesisRegions({ oppId, hypothesisRef, canEdit, rejected, onChanged }: { oppId: string; hypothesisRef: string | null; canEdit: boolean; rejected?: boolean; onChanged?: () => void }) {
  const [h, setH] = useState<Hypothesis | null>(null);
  const [state, setState] = useState<"loading" | "none" | "ready">("loading");
  const [err, setErr] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [target, setTarget] = useState(""), [by, setBy] = useState(""), [review, setReview] = useState("");
  useEffect(() => {
    let live = true;
    if (!hypothesisRef) { setState("none"); return; }
    apiGet<Hypothesis>(`/api/intents/hypotheses/${encodeURIComponent(hypothesisRef)}`)
      .then((r) => { if (live) { setH(r); setState(r.versions.length ? "ready" : "none"); const v = r.versions[r.versions.length - 1]; setTarget(v?.target ? String(v.target.value) : ""); setBy(v?.target?.by ?? ""); setReview(v?.review_date ?? ""); } })
      .catch(() => { if (live) setState("none"); });
    return () => { live = false; };
  }, [hypothesisRef, attempt]);
  const save = (body: Record<string, unknown>) => {
    setErr(null); setToast(null);
    apiSend<unknown>("POST", `/api/intents/opportunities/${encodeURIComponent(oppId)}/hypothesis`, body)
      .then(() => { setToast(H.saved); setAttempt((n) => n + 1); onChanged?.(); })
      .catch((e) => setErr(e instanceof ApiError && e.status !== 0 && e.status < 500 ? e.message : H.couldNot));
  };
  if (state === "loading") return <p className="ds-soft" aria-busy="true">Reading the hypothesis.</p>;
  if (state === "none" || !h) return <Region title={H.hypothesis} open><p>{H.notWritten}</p></Region>;
  const v = h.versions[h.versions.length - 1] as Version;
  const saveTarget = (e: FormEvent) => { e.preventDefault(); save({ target: { value: Number(target), by } }); };
  const saveReview = (e: FormEvent) => { e.preventDefault(); save({ review_date: review }); };
  const cc = v.counter_check;
  const line = (l: Line) => {
    const text = l.restricted ? H.noDoc : l.text ?? "";
    const who = l.anonymous ? H.anon : l.by ?? "someone";
    return (
      <li key={l.id}>{l.href && !l.restricted ? <Link to={l.href}>{text}</Link> : text} <span className="ds-soft">({l.stance === "supports" ? H.supports : H.counters}, {who}{l.at ? `, ${when(l.at)}` : ""})</span></li>
    );
  };
  return (
    <>
      <Region title={H.hypothesis} open>
        <p><strong>North.</strong> {v.belief} <span className="ds-soft">A suggestion from North. Version {v.v}, {when(v.at)}.</span></p>
        <p><Chip>{LENSES.find(([k]) => k === v.lens)?.[1] ?? v.lens}</Chip> {v.measure && <span>{H.measure}: {v.measure.name ?? "A restricted measure"}</span>}</p>
        <p>{H.baseline}: {val(v.baseline, v.baseline_missing)}</p>
        <p>{H.target}: {val(v.target, v.target_missing, v.target?.by ? ` by ${v.target.by}` : "")}{v.target?.set_by ? <span className="ds-soft"> (set by {v.target.set_by})</span> : null}</p>
        <p>{H.uplift}: {v.expected_uplift ? `${v.expected_uplift.value} ${v.expected_uplift.unit} per ${v.expected_uplift.per ?? "month"}, ${BASIS[v.expected_uplift.basis ?? ""] ?? v.expected_uplift.basis}` : notYet(v.uplift_missing)}</p>
        <p>{H.confidence}: {v.confidence ? CONFIDENCE[v.confidence] ?? v.confidence : "Not available yet"} · {H.review}: {v.review_date ?? "Not set"}</p>
        {canEdit && (
          <>
            <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>{H.lens}
              <select value={v.lens} onChange={(e) => save({ lens: e.target.value })} style={{ minHeight: 44 }}>{LENSES.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select>
            </label>
            <form onSubmit={saveTarget} style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {!v.target && <span className="ds-soft">{H.noTarget}</span>}
              <label>{H.target}{v.baseline ? ` (${v.baseline.unit})` : ""} <input type="number" step="any" value={target} onChange={(e) => setTarget(e.target.value)} required style={{ minHeight: 44 }} /></label>
              <label>By <input type="date" value={by} onChange={(e) => setBy(e.target.value)} required style={{ minHeight: 44 }} /></label>
              <div><Button type="submit">{H.saveTarget}</Button></div>
            </form>
            <form onSubmit={saveReview} style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <label>{H.review} <input type="date" value={review} onChange={(e) => setReview(e.target.value)} required style={{ minHeight: 44 }} /></label>
              <div><Button type="submit">{H.saveReview}</Button></div>
            </form>
            {err && <p role="alert" className="ds-warn">{err}</p>}
            {toast && <p role="status">{toast}</p>}
          </>
        )}
      </Region>
      <Region title={H.evidence}>
        {H.groups.map(([k, label]) => {
          const ls = (v.evidence ?? []).filter((l) => l.record_kind === k);
          return <div key={k}><h4>{label}</h4>{ls.length ? <ul>{ls.map(line)}</ul> : <p className="ds-soft">{H.noKind}</p>}</div>;
        })}
      </Region>
      <Region title={H.counter}>
        {cc ? (
          <>
            <p><strong>North.</strong> {cc.verdict === "holds" ? H.holds : H.broken}. {cc.why}</p>
            {(cc.looked_for ?? []).length > 0 && <><h4>{H.lookedFor}</h4><ul>{(cc.looked_for ?? []).map((x, i) => <li key={i}>{x}</li>)}</ul></>}
            {(cc.found ?? []).length > 0 && <><h4>{H.found}</h4><ul>{(cc.found ?? []).map((x, i) => <li key={i}>{x}</li>)}</ul></>}
          </>
        ) : <p>{H.notChecked}</p>}
      </Region>
      {v.theme && (
        <Region title={H.voices}>
          <p>{v.theme.voices} {v.theme.voices === 1 ? "voice" : "voices"}</p>
          <ul>{Object.entries(v.theme.by_source).filter(([, n]) => n > 0).map(([k, n]) => <li key={k}>{SOURCE_NAME[k] ?? k}: {n}</li>)}</ul>
          {(h.voices_named ?? []).length > 0 && <p className="ds-soft">Named: {(h.voices_named ?? []).join(", ")}. The rest spoke anonymously.</p>}
        </Region>
      )}
      {rejected && cc?.verdict === "broken" && (
        <p><strong>North.</strong> {H.rejectedBecause}: {cc.why}{cc.broke_by?.length ? <span className="ds-soft"> ({cc.broke_by.length} {cc.broke_by.length === 1 ? "record" : "records"} broke it)</span> : null}</p>
      )}
    </>
  );
}
