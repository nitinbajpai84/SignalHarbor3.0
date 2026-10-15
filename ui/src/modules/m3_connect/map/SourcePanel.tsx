import { useState, type FormEvent } from "react";

import { ApiError } from "../../../api/client";
import Panel from "../../../components/Panel";
import ScreenState from "../../../components/ScreenState";
import { useLoad } from "../../m1_intent/useLoad";
import { getSource, moveSource, type Reason } from "../api";
import { mapCopy as t } from "./copy";
import { markLines } from "./SourceMapChart";

const p = t.panel;

function Reasons({ title, rating, reasons }: { title: string; rating: number; reasons: Reason[] }) {
  return (
    <div>
      <h3>{`${title} ${rating.toFixed(1)}`}</h3>
      <ul>
        {reasons.map((r, i) => (
          <li key={i}>
            {r.text} <span className="n-muted">({r.effect === "raises" ? p.raises : p.lowers})</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function MoveForm({ assessmentId, sourceId, draft, onMoved }: { assessmentId: string; sourceId: string; draft?: { impact: number; readiness: number }; onMoved: () => void }) {
  const [impact, setImpact] = useState("");
  const [readiness, setReadiness] = useState("");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState("");
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const nums = [impact, readiness].map((v) => (v.trim() === "" ? undefined : Number(v)));
    if (nums.every((n) => n === undefined)) return setProblem(t.move.needValue);
    if (nums.some((n) => n !== undefined && !(n >= -1 && n <= 1))) return setProblem(t.move.range);
    if (!reason.trim()) return setProblem(t.move.needReason);
    setBusy(true);
    setProblem("");
    try {
      await moveSource(assessmentId, sourceId, {
        ...(nums[0] === undefined ? {} : { impact: nums[0] }),
        ...(nums[1] === undefined ? {} : { readiness: nums[1] }),
        reason: reason.trim(),
      });
      setImpact("");
      setReadiness("");
      setReason("");
      onMoved();
    } catch (err) {
      setProblem(err instanceof ApiError && err.status !== 0 && err.status < 500 ? err.message : t.move.failed);
    } finally {
      setBusy(false);
    }
  };
  return (
    <form onSubmit={submit} noValidate aria-label={t.move.title}>
      <h3>{t.move.title}</h3>
      <p className="n-muted">{t.move.help}</p>
      {draft ? <p className="n-muted">{t.move.draftWas(draft.impact, draft.readiness)}</p> : null}
      <label>
        {t.move.impact}
        <input type="number" min={-1} max={1} step={0.1} value={impact} onChange={(e) => setImpact(e.target.value)} />
      </label>
      <label>
        {t.move.readiness}
        <input type="number" min={-1} max={1} step={0.1} value={readiness} onChange={(e) => setReadiness(e.target.value)} />
      </label>
      <label>
        {t.move.reason}
        <textarea value={reason} onChange={(e) => setReason(e.target.value)} maxLength={500} />
      </label>
      {problem ? <p role="alert" className="state state-error">{problem}</p> : null}
      <button type="submit" className="n-btn primary" disabled={busy}>
        {busy ? t.move.saving : t.move.save}
      </button>
    </form>
  );
}

export default function SourcePanel({ assessmentId, sourceId, version, onClose, onMoved }: {
  assessmentId: string; sourceId: string; version: number; onClose: () => void; onMoved: () => void;
}) {
  const s = useLoad(() => getSource(assessmentId, sourceId), `m3-source-${assessmentId}-${sourceId}-${version}`);
  const d = s.data;
  return (
    <Panel title={d ? d.source.name : p.title} eyebrow={p.title} actions={<button type="button" className="n-btn" onClick={onClose}>{p.close}</button>}>
      <ScreenState state={s.state} message={s.state === "loading" ? p.loading : s.message} onRetry={s.retry}>
        {d && d.source.restricted ? <p>{p.restricted}</p> : null}
        {d && !d.source.restricted ? (
          <>
            <p><strong>{d.source.zone_label}</strong> · {t.kinds[d.source.kind]} · {t.measures(d.source.measures_fed)}</p>
            {d.source.override ? <p><strong>{t.moved(d.source.override.by)}</strong>: {d.source.override.reason}</p> : null}
            {d.source.summary ? <p>{d.source.summary} <span className="n-muted">({t.suggestion})</span></p> : null}
            <ul>{markLines(d.source).map((m) => <li key={m}>{m}</li>)}</ul>
            <Reasons title={p.impact} rating={d.source.impact} reasons={d.impact_reasons} />
            <Reasons title={p.readiness} rating={d.source.readiness} reasons={d.readiness_reasons} />
            <h3>{p.missing}</h3>
            {d.missing.length ? <ul>{d.missing.map((m) => <li key={m}>{m}</li>)}</ul> : <p>{p.nothingMissing}</p>}
            <h3>{p.measures}</h3>
            {d.measures.length ? (
              <ul>
                {d.measures.map((m) => (
                  <li key={m.id}>
                    {m.name} ({m.priority ?? "No priority set"}). {p.owners}: {Object.values(m.owners).filter(Boolean).join(", ") || p.noMeasures}
                  </li>
                ))}
              </ul>
            ) : <p>{p.noMeasures}</p>}
            <h3>{p.tables}</h3>
            {d.tables.length ? d.tables.map((tb) => (
              <div key={tb.name}>
                <strong>{tb.name}</strong>
                <ul>{tb.fields.map((f) => <li key={f.name}>{f.name}{f.type ? ` (${f.type})` : ""}{f.meaning ? `: ${f.meaning}` : ""}</li>)}</ul>
              </div>
            )) : <p>{p.noTables}</p>}
            <MoveForm assessmentId={assessmentId} sourceId={sourceId} draft={d.source.draft} onMoved={onMoved} />
          </>
        ) : null}
      </ScreenState>
    </Panel>
  );
}
