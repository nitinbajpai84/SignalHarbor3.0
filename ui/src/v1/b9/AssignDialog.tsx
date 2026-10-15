import { useEffect, useState } from "react";

import { ApiError } from "../../api/client";
import { Button } from "../../design";
import { useSession } from "../../useSession";
import { assignSteps, initials, listCandidates, nice, type Candidate } from "./api";
import { ASSIGNABLE, stepName, type StepId } from "./steps";
import "./b9.css";

// V5 design A5: "Assign a step". Choose the steps, who builds them, a note and a due date. The owner stays the owner.
// "Hand over" is the same dialog with Architecture and Pipelines chosen. The server (package V5W-1) sends it to the builder's Action list.
export default function AssignDialog({ pid, title, preset, handover, people, onClose, onDone }: {
  pid: string; title: string; preset: StepId[]; handover?: boolean; people?: { head_of_data?: string | null; builder?: string | null };
  onClose: () => void; onDone: () => void;
}) {
  const me = useSession().user;
  const [steps, setSteps] = useState<StepId[]>(preset);
  const [cands, setCands] = useState<Candidate[] | null>(null);
  const [to, setTo] = useState("");
  const [note, setNote] = useState("");
  const [due, setDue] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let live = true;
    listCandidates(pid).then((r) => live && setCands(r.people ?? [])).catch(() => live && setCands([])); // without the list, the people the project names are offered
    return () => { live = false; };
  }, [pid]);

  const own: Candidate[] = [people?.builder, people?.head_of_data].filter((x): x is string => !!nice(x)).map((n) => ({ id: n, name: nice(n) }));
  const list: Candidate[] = [...(cands && cands.length ? cands : own), { id: me?.account_id ?? me?.display_name ?? "me", name: "Me", role: `${me?.display_name ?? "You"}: you would check Span's draft yourself` }];
  const chosen = list.find((c) => c.id === to);
  const toggle = (s: StepId) => setSteps((x) => (x.includes(s) ? x.filter((y) => y !== s) : [...x, s]));

  async function send() {
    if (!chosen || !steps.length) return;
    setBusy(true); setError("");
    try {
      await assignSteps(pid, { steps, to: chosen.id, ...(note.trim() ? { note: note.trim() } : {}), ...(due ? { due } : {}), ...(handover ? { handover: true } : {}) });
      onDone();
    } catch (e) {
      setError(e instanceof ApiError && e.message ? e.message : "That did not go through. Please try again.");
    } finally { setBusy(false); }
  }

  return (
    <div className="b9-scrim" role="presentation">
      <div className="b9-dialog" role="dialog" aria-modal="true" aria-labelledby="b9-assign-h">
        <span className="b9-eyebrow">{handover ? "PROJECT · HAND OVER" : "PROJECT · ASSIGN"}</span>
        <h2 id="b9-assign-h" style={{ margin: 0 }}>{handover ? "Hand the build to the data team" : "Assign a step"}</h2>
        <p className="ds-muted" style={{ margin: 0 }}>{title}. You stay the owner.</p>
        <fieldset>
          <legend>Which steps</legend>
          {ASSIGNABLE.map((s) => <label key={s}><input type="checkbox" checked={steps.includes(s)} onChange={() => toggle(s)} /> {stepName(s)}</label>)}
        </fieldset>
        <fieldset>
          <legend>Who</legend>
          {cands === null ? <span className="ds-muted" role="status">Loading the people.</span> : null}
          {list.map((c) => (
            <label key={c.id} style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <input type="radio" name="b9-who" checked={to === c.id} onChange={() => setTo(c.id)} aria-label={c.name} />
              <span className="b9-person"><b>{initials(c.name)}</b><span>{c.name}{c.role || c.open_steps !== undefined ? <small>{[c.role, c.open_steps !== undefined ? `${c.open_steps} ${c.open_steps === 1 ? "step" : "steps"} open this week` : ""].filter(Boolean).join(" · ")}</small> : null}</span></span>
            </label>
          ))}
        </fieldset>
        <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>Note to the builder
          <textarea rows={3} value={note} onChange={(e) => setNote(e.target.value)} placeholder="What should they check first?" />
        </label>
        <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>Due date
          <input type="date" value={due} onChange={(e) => setDue(e.target.value)} />
        </label>
        <p className="ds-muted" style={{ margin: 0 }}>{chosen ? `${chosen.name} sees this in Action under Needs me, with the signed intent and your note. The head of data still approves.` : "Choose who builds it."}</p>
        {error ? <p role="alert" style={{ margin: 0 }}>{error}</p> : null}
        <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
          <Button onClick={onClose}>Cancel</Button>
          <Button variant="primary" disabled={busy || !chosen || !steps.length} onClick={() => void send()}>{chosen ? `${handover ? "Hand over to" : "Assign to"} ${chosen.name}` : handover ? "Hand over" : "Assign"}</Button>
        </div>
      </div>
    </div>
  );
}
