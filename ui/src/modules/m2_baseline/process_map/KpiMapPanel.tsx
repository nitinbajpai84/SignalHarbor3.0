import { useState, type FormEvent } from "react";

import { ApiError } from "../../../api/client";
import Panel from "../../../components/Panel";
import ScreenState from "../../../components/ScreenState";
import { addStep, editStep, removeStep, setTracking, validateStep, type KpiMap, type ProcessMap, type TrackingId } from "../api";
import { mapCopy as t } from "../copy";
import Swimlane, { stepFigure, stepSource, type StatusLabels } from "./Swimlane";

interface Props {
  baselineId: string;
  kpi: KpiMap;
  statuses: ProcessMap["statuses"];
  signed: boolean;
  /** The server's answer after a change: the screen swaps this measure's map for it. */
  onChange: (kpi: KpiMap) => void;
}

const plain = (e: unknown) => (e instanceof ApiError && e.message ? e.message : t.notStated);

export default function KpiMapPanel({ baselineId, kpi, statuses, signed, onChange }: Props) {
  const labels = Object.fromEntries(statuses.map((s) => [s.id, s.label])) as StatusLabels;
  const [selected, setSelected] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({ lane: "", text: "", manual: false });
  const [problem, setProblem] = useState<string | null>(null);
  const step = kpi.steps.find((s) => s.id === selected) ?? null;

  const run = async (call: () => Promise<KpiMap>, then?: () => void) => {
    setProblem(null);
    try {
      onChange(await call());
      then?.();
    } catch (e) {
      setProblem(plain(e));
    }
  };
  const pick = (id: string) => {
    setSelected(id);
    setEditing(false);
  };
  const startEdit = () => {
    if (!step) return;
    setForm({ lane: step.lane, text: step.text, manual: step.manual });
    setEditing(true);
  };
  const saveEdit = (e: FormEvent) => {
    e.preventDefault();
    if (step) void run(() => editStep(baselineId, kpi.id, step.id, form), () => setEditing(false));
  };
  const [add, setAdd] = useState({ lane: "", text: "", manual: false });
  const submitAdd = (e: FormEvent) => {
    e.preventDefault();
    void run(() => addStep(baselineId, kpi.id, add), () => setAdd({ lane: "", text: "", manual: false }));
  };

  const tr = kpi.tracking;
  const [track, setTrack] = useState({
    status: (tr.status.value ?? "") as TrackingId | "",
    date: tr.tentative_date.value ?? "",
    next: tr.next_step.value ?? "",
  });
  const saveTracking = (e: FormEvent) => {
    e.preventDefault();
    if (track.status) void run(() => setTracking(baselineId, kpi.id, { status: track.status as TrackingId, tentative_date: track.date, next_step: track.next }));
  };
  const lens = kpi.counts.answers > 0 ? t.lens(kpi.counts.answers, kpi.counts.to_confirm, kpi.counts.manual) : t.lensPack;

  return (
    <>
      <Panel title={kpi.name ?? t.title} eyebrow={t.panelEyebrow} label={`${t.panelTitle}: ${kpi.name ?? ""}`}>
        {!kpi.drawn ? (
          <ScreenState state="empty" message={t.notDrawn} />
        ) : kpi.steps.length === 0 ? (
          <ScreenState state="empty" message={t.noSteps} />
        ) : (
          <>
            <div className="n-suggest-block" style={{ marginBottom: 12 }}>
              <div className="n-suggest-label">{t.lensLabel}</div>
              <div>{lens}</div>
            </div>
            {kpi.steps.every((s) => s.id.startsWith("wait-")) ? <p className="n-muted">{t.noStepsYet}</p> : null}
            <Swimlane kpi={kpi} labels={labels} selected={selected} onSelect={pick} />
          </>
        )}
        {kpi.removed > 0 ? <p className="n-muted">{t.removedNote(kpi.removed)}</p> : null}
        {problem ? (
          <p role="alert" className="state state-error">
            {problem}
          </p>
        ) : null}
        {step ? (
          <div className="n-stack" style={{ marginTop: 12 }} role="group" aria-label={t.selected}>
            <strong>{step.text}</strong>
            <span className="n-muted">
              {step.lane} · {stepSource(step)} · {stepFigure(step, labels)}
            </span>
            {signed ? null : editing ? (
              <form onSubmit={saveEdit} className="n-stack">
                <label>
                  {t.lane}
                  <input className="n-input" value={form.lane} onChange={(e) => setForm({ ...form, lane: e.target.value })} />
                </label>
                <label>
                  {t.what}
                  <input className="n-input" value={form.text} onChange={(e) => setForm({ ...form, text: e.target.value })} />
                </label>
                <label className="m1-choice">
                  <input type="checkbox" checked={form.manual} onChange={(e) => setForm({ ...form, manual: e.target.checked })} />
                  {t.isManual}
                </label>
                <div className="n-flex">
                  <button type="submit" className="n-btn primary">
                    {t.save}
                  </button>
                  <button type="button" className="n-btn ghost" onClick={() => setEditing(false)}>
                    {t.cancel}
                  </button>
                </div>
              </form>
            ) : (
              <div className="n-flex wrap">
                <button type="button" className="n-btn" onClick={() => void run(() => validateStep(baselineId, kpi.id, step.id))}>
                  {t.confirm}
                </button>
                <button type="button" className="n-btn" onClick={startEdit}>
                  {t.edit}
                </button>
                <button type="button" className="n-btn ghost" onClick={() => void run(() => removeStep(baselineId, kpi.id, step.id), () => setSelected(null))}>
                  {t.remove}
                </button>
              </div>
            )}
          </div>
        ) : null}
      </Panel>

      {signed ? null : (
        <Panel title={t.addTitle} tight>
          <form onSubmit={submitAdd} className="n-stack">
            <label>
              {t.lane}
              <input className="n-input" value={add.lane} onChange={(e) => setAdd({ ...add, lane: e.target.value })} />
            </label>
            <label>
              {t.what}
              <input className="n-input" value={add.text} onChange={(e) => setAdd({ ...add, text: e.target.value })} />
            </label>
            <label className="m1-choice">
              <input type="checkbox" checked={add.manual} onChange={(e) => setAdd({ ...add, manual: e.target.checked })} />
              {t.isManual}
            </label>
            <div>
              <button type="submit" className="n-btn">
                {t.add}
              </button>
            </div>
          </form>
        </Panel>
      )}

      <Panel title={t.trackingTitle} eyebrow={t.trackingEyebrow} tight>
        <form onSubmit={saveTracking} className="n-stack">
          <label>
            {t.status}
            <select className="n-select" value={track.status} onChange={(e) => setTrack({ ...track, status: e.target.value as TrackingId | "" })} disabled={signed}>
              <option value="">{t.chooseStatus}</option>
              {statuses.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.label}
                </option>
              ))}
            </select>
          </label>
          <label>
            {t.tentativeDate}
            <input className="n-input" type="date" value={track.date} onChange={(e) => setTrack({ ...track, date: e.target.value })} disabled={signed} />
          </label>
          <label>
            {t.nextStep}
            <input className="n-input" value={track.next} onChange={(e) => setTrack({ ...track, next: e.target.value })} disabled={signed} />
          </label>
          {signed ? null : (
            <div>
              <button type="submit" className="n-btn" disabled={!track.status}>
                {t.save}
              </button>
            </div>
          )}
        </form>
      </Panel>
    </>
  );
}
