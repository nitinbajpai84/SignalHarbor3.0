import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError } from "../../../api/client";
import Panel from "../../../components/Panel";
import ScreenState, { type ScreenStateName } from "../../../components/ScreenState";
import StatusPill from "../../../components/StatusPill";
import { useLoad } from "../../../components/useLoad";
import { CHANGED, notifyChanged } from "../api";
import { m2Tech as t } from "./copy";
import QuestionItem from "./QuestionItem";
import {
  confirmTechnical,
  getTechnical,
  LINK_PARTS,
  lensTechnical,
  putPart,
  redraftTechnical,
  usePart,
  type TechKpi,
  type TechPartView,
  type TechnicalScreen,
} from "./technicalApi";

const TONE = { stated: "success", guessed: "warning", unknown: "muted" } as const;
const steps = (text: string) => text.split("\n").map((l) => l.replace(/^\s*\d+[.)]\s*/, "")).filter(Boolean);
const asText = (v: string | string[] | null) => (Array.isArray(v) ? v.join(", ") : v ?? "");

function Shown({ p, baselineId }: { p: TechPartView; baselineId: string }) {
  const c = p.cell;
  if (p.withheld) return <span className="n-muted">{t.withheld}</span>;
  if (c.mark === "unknown" || !asText(c.value)) return <span className="n-muted">{c.from ? `${t.notAvailable}. ${c.from}` : t.notAvailable}</span>;
  if (LINK_PARTS.includes(p.part))
    return (
      <span>
        {p.links.map((l, i) => (
          <span key={l.id}>
            {i ? ", " : ""}
            <Link to={`/modules/m2_baseline/catalogue/${baselineId}?tab=${p.part}`} title={t.inCatalogue}>{l.name}</Link>
          </span>
        ))}
      </span>
    );
  if (p.part === "calculation") return <ol style={{ margin: 0, paddingLeft: 20 }}>{steps(String(c.value)).map((s, i) => <li key={i}>{s}</li>)}</ol>;
  return <span>{asText(c.value)}</span>;
}

/** One part of the technical definition, with the three things a person can do to it, as for the business definition: use Lens's draft,
 * edit it, or tell Lens what to change. Every part says how sure it is, who said it and where it came from. */
function PartRow({ baselineId, kpi, p, locked, onScreen }: { baselineId: string; kpi: TechKpi; p: TechPartView; locked: boolean; onScreen: (s: TechnicalScreen) => void }) {
  const [mode, setMode] = useState<"edit" | "tell" | null>(null);
  const [text, setText] = useState("");
  const [mark, setMark] = useState<"stated" | "guessed">("stated");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const isLink = LINK_PARTS.includes(p.part);
  const run = async (job: Promise<TechnicalScreen>) => {
    setBusy(true);
    setError(null);
    try {
      onScreen(await job);
      setMode(null);
      notifyChanged();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : t.error);
    } finally {
      setBusy(false);
    }
  };
  const save = () => {
    const value = isLink ? text.split(/[,;\s]+/).filter(Boolean) : text;
    return run(putPart(baselineId, kpi.kpi_id, p.part, value, text.trim() ? mark : "unknown"));
  };
  return (
    <li aria-label={p.label} style={{ display: "grid", gap: 6, borderBottom: "1px solid var(--border-hairline)", paddingBottom: 8 }}>
      <div className="n-flex wrap">
        <strong>{p.label}</strong>
        <StatusPill tone={TONE[p.cell.mark]}>{t.marks[p.cell.mark]}</StatusPill>
        {p.cell.mark !== "unknown" && p.cell.by ? <span className="n-muted">{t.by(p.cell.by)}{p.cell.from ? ` · ${t.from(p.cell.from)}` : ""}</span> : null}
      </div>
      <Shown p={p} baselineId={baselineId} />
      {(p.history ?? []).map((h, i) => <p key={i} className="n-muted">{t.history(asText(h.value))}</p>)}
      {p.proposal ? (
        <div className="n-suggest-block">
          <div className="n-suggest-label">{t.suggestion}</div>
          <p>{asText(p.proposal.value)}</p>
          <button type="button" className="n-btn sm" disabled={locked || busy} aria-label={`${t.useThis}: ${p.label}`} onClick={() => void run(usePart(baselineId, kpi.kpi_id, p.part))}>{t.useThis}</button>
        </div>
      ) : null}
      <div className="n-flex wrap">
        <button type="button" className="n-btn sm" disabled={locked} aria-label={`${t.edit}: ${p.label}`} onClick={() => { setMode("edit"); setText(p.withheld ? "" : isLink ? p.links.map((l) => l.id).join(", ") : asText(p.cell.value)); setMark(p.cell.mark === "guessed" ? "guessed" : "stated"); }}>{t.edit}</button>
        <button type="button" className="n-btn sm" disabled={locked} aria-label={`${t.tell}: ${p.label}`} onClick={() => { setMode("tell"); setText(""); }}>{t.tell}</button>
      </div>
      {mode === "edit" ? (
        <div className="n-flex wrap">
          <textarea className="n-input" rows={p.part === "calculation" ? 4 : 2} aria-label={`${t.edit}: ${p.label}`} value={text} onChange={(e) => setText(e.target.value)} />
          <select className="n-select" aria-label={`${p.label}: ${t.marks.stated}`} value={mark} onChange={(e) => setMark(e.target.value as "stated" | "guessed")}>
            <option value="stated">{t.marks.stated}</option>
            <option value="guessed">{t.marks.guessed}</option>
          </select>
          <button type="button" className="n-btn sm primary" disabled={busy} onClick={() => void save()}>{t.save}</button>
          <button type="button" className="n-btn sm" onClick={() => setMode(null)}>{t.cancel}</button>
          {isLink ? <span className="n-muted">{t.linkHelp}</span> : null}
        </div>
      ) : null}
      {mode === "tell" ? (
        <div className="n-flex wrap">
          <input className="n-input" aria-label={`${t.tell}: ${p.label}`} placeholder={t.tellPlaceholder} value={text} onChange={(e) => setText(e.target.value)} />
          <button type="button" className="n-btn sm primary" disabled={busy || !text.trim()} onClick={() => void run(redraftTechnical(baselineId, kpi.kpi_id, `${p.label}: ${text}`))}>{t.tellSend}</button>
          <button type="button" className="n-btn sm" onClick={() => setMode(null)}>{t.cancel}</button>
        </div>
      ) : null}
      {error ? <p role="alert" className="state state-error">{error}</p> : null}
    </li>
  );
}

/** M2-E1, under the business definition of one measure: its technical definition (sources, tables and fields as links into the catalogue, the
 * calculation in steps, filters, grain, period, currency basis) and its open questions. One load serves both. */
export default function TechnicalSection({ baselineId, kpiId, locked, governor }: { baselineId: string; kpiId: string; locked: boolean; governor: boolean }) {
  const loaded = useLoad(() => getTechnical(baselineId), `m2-tech-${baselineId}`);
  const [fresh, setFresh] = useState<TechnicalScreen | null>(null);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    const again = () => getTechnical(baselineId).then(setFresh).catch(() => undefined);
    window.addEventListener(CHANGED, again);
    return () => window.removeEventListener(CHANGED, again);
  }, [baselineId]);
  const data = fresh ?? loaded.data;
  const kpi = data?.kpis.find((k) => k.kpi_id === kpiId);
  const items = (data?.ambiguities ?? []).filter((a) => a.kpi_id === kpiId);
  const blank = !!kpi && kpi.parts.every((p) => p.cell.mark === "unknown" && !p.proposal);
  const state: ScreenStateName = fresh ? "populated" : loaded.state;

  const draft = async () => {
    setBusy(true);
    setError(null);
    try {
      const s = await lensTechnical(baselineId, [kpiId], true);
      setFresh(s);
      setNote(s.lens_note ?? "");
      notifyChanged();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : t.error);
    } finally {
      setBusy(false);
    }
  };
  const confirm = async () => {
    setError(null);
    try {
      setFresh(await confirmTechnical(baselineId, kpiId));
      notifyChanged();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : t.error);
    }
  };

  return (
    <>
      <Panel
        title={t.title}
        actions={kpi ? <StatusPill tone={kpi.ready.ready ? "success" : "warning"}>{kpi.ready.label}</StatusPill> : undefined}
      >
        <ScreenState state={state} message={loaded.state === "loading" ? t.loading : loaded.state === "refused" ? t.refused : loaded.state === "error" ? t.loadFailed : undefined} onRetry={loaded.retry}>
          {kpi ? (
            <>
              <p className="n-muted">{t.help}</p>
              {blank ? (
                <div className="n-empty">
                  <p className="ebody">{t.empty}</p>
                  <button type="button" className="n-btn" disabled={locked || busy} onClick={() => void draft()}>{t.draft}</button>
                </div>
              ) : null}
              {note ? <p role="status" className="n-muted">{note}</p> : null}
              <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: 10 }}>
                {kpi.parts.map((p) => (
                  <PartRow key={`${p.part}-${p.cell.at}-${p.proposal?.at ?? ""}`} baselineId={baselineId} kpi={kpi} p={p} locked={locked} onScreen={setFresh} />
                ))}
              </ul>
              <div className="n-flex wrap">
                {kpi.confirmed ? <span>{t.confirmedBy(kpi.confirmed.by, kpi.confirmed.at)}</span> : <span className="n-muted">{t.notConfirmed}</span>}
                {!kpi.confirmed && kpi.to_confirm?.length ? <span className="n-muted">{t.toConfirm(kpi.to_confirm.join(", "))}{kpi.confirmed_parts?.length ? `. ${t.confirmedParts(kpi.confirmed_parts.join(", "))}` : ""}</span> : null}
                {kpi.complete && !kpi.confirmed ? <button type="button" className="n-btn sm primary" disabled={locked} onClick={() => void confirm()}>{t.confirm}</button> : null}
                {!kpi.complete ? <span className="n-muted">{kpi.missing.join(", ")}</span> : null}
              </div>
              {error ? <p role="alert" className="state state-error">{error}</p> : null}
            </>
          ) : state === "populated" ? (
            <p className="n-muted">{t.refused}</p>
          ) : null}
        </ScreenState>
      </Panel>
      {kpi ? (
        <Panel title={t.open.title}>
          {items.length === 0 ? (
            <p className="n-muted">{t.open.none}</p>
          ) : (
            <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: 10 }}>
              {items.map((a) => (
                <QuestionItem key={`${a.id}-${a.status}-${a.asked?.at ?? ""}`} baselineId={baselineId} item={a} kpi={kpi} locked={locked} governor={governor} onScreen={setFresh} />
              ))}
            </ul>
          )}
        </Panel>
      ) : null}
    </>
  );
}
