import { useState } from "react";

import Panel from "../../../components/Panel";
import StatusPill from "../../../components/StatusPill";
import { dateOrNone } from "../plainText";
import { planCopy as T } from "./copy";
import type { Band, Effort, ItemChange, PlanItem, PlanView } from "./planApi";

const BANDS: Band[] = ["now", "next", "later"];
const EFFORTS: Effort[] = ["small", "medium", "large"];

interface Props {
  plan: PlanView;
  disabled: boolean;
  onEdit: (change: ItemChange) => Promise<boolean>;
  onRedraft: () => void;
}

/** The three bands as columns of cards (deck slide "The phased build plan"): Now (weeks 0 to 3), Next (3 to 8), Later (8 and beyond). */
export default function BandsPanel({ plan, disabled, onEdit, onRedraft }: Props) {
  return (
    <Panel
      title={T.plan.title}
      actions={
        !disabled ? (
          <button type="button" className="n-btn sm" onClick={onRedraft}>
            {T.plan.redraft}
          </button>
        ) : null
      }
    >
      <p className="n-muted">{T.suggestion}</p>
      <div style={{ display: "grid", gap: 16, gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", alignItems: "start" }}>
        {BANDS.map((b) => (
          <section key={b} aria-label={plan.bands_info[b].label} style={{ display: "grid", gap: 10 }}>
            <header>
              <h3 style={{ margin: 0 }}>{plan.bands_info[b].label}</h3>
              <span className="n-e1-def-note">{plan.bands_info[b].weeks}</span>
            </header>
            {plan.bands[b].length === 0 ? <p className="state n-muted">{T.plan.none}</p> : null}
            {plan.bands[b].map((it) => (
              <Card key={it.key} it={it} plan={plan} disabled={disabled} onEdit={onEdit} />
            ))}
          </section>
        ))}
      </div>
    </Panel>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="n-e1-def-note">
      <strong>{label}:</strong> {value}
    </div>
  );
}

function Card({ it, plan, disabled, onEdit }: { it: PlanItem; plan: PlanView; disabled: boolean; onEdit: Props["onEdit"] }) {
  const [editing, setEditing] = useState(false);
  if (it.restricted) {
    return (
      <article className="n-panel tight" style={{ padding: 12 }}>
        <strong>{T.plan.restrictedCard}</strong>
      </article>
    );
  }
  const band = it.band;
  const edits = Object.values(it.edits ?? {});
  const names = it.measures.map((m) => m.name).join(", ");
  return (
    <article className="n-panel tight" style={{ padding: 12, display: "grid", gap: 6 }}>
      <strong>{it.summary}</strong>
      <Row label={T.plan.measures} value={names} />
      {it.pain_points.length ? <Row label={T.plan.resolves} value={it.pain_points.map((p) => p.title).join(", ")} /> : null}
      <Row label={T.plan.effort} value={it.effort_label ?? ""} />
      <Row label={T.plan.team} value={it.team.join(", ")} />
      {band === "next" ? (
        <>
          <Row label={T.plan.blockedBy} value={it.blocked_by.join("; ")} />
          <Row label={T.plan.whoUnblocks} value={it.who_unblocks.join("; ")} />
          <Row label={T.plan.expected} value={dateOrNone(it.date_text ?? it.date, T.plan.noDate)} />
        </>
      ) : null}
      {band === "later" ? (
        <>
          <Row label={T.plan.whyLater} value={it.why_descoped ?? ""} />
          <Row label={T.plan.affects} value={names} />
          <Row label={T.plan.covered} value={it.covered_text ?? ""} />
        </>
      ) : null}
      {edits[0] ? <div className="n-e1-def-note">{T.plan.editedBy(edits[0].by, edits[0].reason)}</div> : null}
      {it.proposals && Object.keys(it.proposals).length ? (
        <div className="n-e1-def-note">
          {T.plan.proposal(Object.entries(it.proposals).map(([k, v]) => `${k === "effort" ? T.plan.effort.toLowerCase() : k} ${k === "effort" ? plan.effort[v as Effort] ?? String(v) : String(v)}`).join(", "))}
        </div>
      ) : null}
      {it.stale ? <StatusPill tone="warning">{T.plan.stale}</StatusPill> : null}
      {!disabled && !editing ? (
        <div>
          <button type="button" className="n-btn sm" onClick={() => setEditing(true)} aria-label={`${T.plan.edit}: ${names}`}>
            {T.plan.edit}
          </button>
        </div>
      ) : null}
      {editing ? <Editor it={it} onClose={() => setEditing(false)} onEdit={onEdit} /> : null}
    </article>
  );
}

function Editor({ it, onClose, onEdit }: { it: PlanItem; onClose: () => void; onEdit: Props["onEdit"] }) {
  const [band, setBand] = useState<Band>(it.band);
  const [effort, setEffort] = useState<Effort>(it.effort ?? "medium");
  const [team, setTeam] = useState(it.team.join(", "));
  const [date, setDate] = useState(it.date ?? "");
  const [covered, setCovered] = useState(it.covered_by ?? "");
  const [reason, setReason] = useState("");
  const [problem, setProblem] = useState("");
  const names = it.measures.map((m) => m.name).join(", ");
  const save = async () => {
    const change: ItemChange = { key: it.key, reason: reason.trim() };
    if (band !== it.band) change.band = band;
    if (effort !== it.effort) change.effort = effort;
    if (team.trim() !== it.team.join(", ")) change.team = team.trim();
    if (date !== (it.date ?? "")) change.date = date;
    if (covered.trim() !== (it.covered_by ?? "")) change.covered_by = covered.trim();
    if (Object.keys(change).length === 2) return setProblem(T.plan.nothingChanged);
    if (!change.reason) return setProblem(T.plan.needReason);
    setProblem("");
    if (await onEdit(change)) onClose();
  };
  const id = (n: string) => `${it.key}-${n}`;
  return (
    <fieldset style={{ display: "grid", gap: 6, border: 0, padding: 0 }}>
      <legend className="n-e1-def-name">{`${T.plan.editTitle}: ${names}`}</legend>
      <label htmlFor={id("band")}>{T.plan.band}</label>
      <select id={id("band")} className="n-input" value={band} onChange={(e) => setBand(e.target.value as Band)}>
        {BANDS.map((b) => (
          <option key={b} value={b}>
            {T.plan.bands[b]}
          </option>
        ))}
      </select>
      <label htmlFor={id("effort")}>{T.plan.effort}</label>
      <select id={id("effort")} className="n-input" value={effort} onChange={(e) => setEffort(e.target.value as Effort)}>
        {EFFORTS.map((x) => (
          <option key={x} value={x}>
            {T.plan.efforts[x]}
          </option>
        ))}
      </select>
      <label htmlFor={id("team")}>{T.plan.team}</label>
      <input id={id("team")} className="n-input" value={team} onChange={(e) => setTeam(e.target.value)} />
      <label htmlFor={id("date")}>{T.plan.date}</label>
      <input id={id("date")} className="n-input" type="date" value={date} onChange={(e) => setDate(e.target.value)} />
      <label htmlFor={id("covered")}>{T.plan.coveredBy}</label>
      <input id={id("covered")} className="n-input" value={covered} onChange={(e) => setCovered(e.target.value)} />
      <label htmlFor={id("reason")}>{T.plan.reason}</label>
      <input id={id("reason")} className="n-input" value={reason} maxLength={400} onChange={(e) => setReason(e.target.value)} aria-describedby={id("help")} />
      <span id={id("help")} className="n-e1-def-note">
        {T.plan.reasonHelp}
      </span>
      {problem ? <p role="alert" className="state state-error">{problem}</p> : null}
      <div className="n-flex" style={{ gap: 8 }}>
        <button type="button" className="n-btn primary sm" onClick={save}>
          {T.plan.save}
        </button>
        <button type="button" className="n-btn sm" onClick={onClose}>
          {T.plan.cancel}
        </button>
      </div>
    </fieldset>
  );
}
