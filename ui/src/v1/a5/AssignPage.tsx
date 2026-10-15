import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";

import { ApiError } from "../../api/client";
import { Button, PageFrame } from "../../design";
import { assignSteps, getAssignments, getPeople, handOver, type ProjectAssignments } from "../p2/api";

// V5W-1: /centre/action/assign/:pid (and ?mode=handover). Designs A5 "Assign a step" and B4 "Hand over the build". Build's project page links here.
const plain = (e: unknown) => (e instanceof ApiError && e.message ? e.message : "That did not go through. Please try again.");

export default function AssignPage() {
  const { pid = "" } = useParams();
  const go = useNavigate();
  const handover = useSearchParams()[0].get("mode") === "handover";
  const [proj, setProj] = useState<ProjectAssignments | null>(null);
  const [people, setPeople] = useState<string[]>([]);
  const [steps, setSteps] = useState<string[]>([]);
  const [to, setTo] = useState("");
  const [message, setMessage] = useState("");
  const [due, setDue] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    getAssignments(pid).then((p) => { setProj(p); setSteps(p.steps.map((s) => s.id)); }, (e) => setError(plain(e)));
    getPeople().then((p) => setPeople(p.map((x) => x.name)), () => undefined);
  }, [pid]);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(""); setBusy(true);
    const body = { steps: handover ? undefined : steps, to, message, due: due || null };
    try {
      await (handover ? handOver(pid, body) : assignSteps(pid, body));
      go("/centre/action");
    } catch (err) { setError(plain(err)); setBusy(false); }
  }
  const title = handover ? "Hand over the project" : "Assign a step";
  const ready = !!to && (handover || steps.length > 0);
  return (
    <PageFrame title={title} subline={proj ? `${proj.project.title ?? "This project"}. You stay the owner.` : "Choose who takes it on."} crumbs={<Link to="/centre/action">Action</Link>}>
      {error ? <p role="alert">{error}</p> : null}
      {proj ? (
        <form onSubmit={submit} style={{ display: "grid", gap: 16, maxWidth: 560 }}>
          {handover ? null : (
            <fieldset style={{ border: 0, padding: 0 }}>
              <legend>Which steps</legend>
              {proj.steps.map((s) => (
                <label key={s.id} style={{ display: "block" }}>
                  <input type="checkbox" checked={steps.includes(s.id)} onChange={(e) => setSteps(e.target.checked ? [...steps, s.id] : steps.filter((x) => x !== s.id))} /> {s.label}
                </label>))}
            </fieldset>)}
          <label>Who
            <select className="ds-input" value={to} onChange={(e) => setTo(e.target.value)} style={{ display: "block" }}>
              <option value="">Choose a person</option>
              {people.map((p) => <option key={p} value={p}>{p}</option>)}
            </select>
          </label>
          <label>Message
            <textarea className="ds-input" rows={4} value={message} onChange={(e) => setMessage(e.target.value)} maxLength={2000} style={{ display: "block", width: "100%" }} />
          </label>
          <label>Due date
            <input className="ds-input" type="date" value={due} onChange={(e) => setDue(e.target.value)} style={{ display: "block" }} />
          </label>
          <p className="ds-muted" style={{ margin: 0 }}>{to || "They"} will see this in Action under Assigned to me, with your message. You will see it under Waiting on others.</p>
          <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
            <Link className="ds-link" to="/centre/action">Cancel</Link>
            <Button type="submit" variant="primary" disabled={!ready || busy}>{handover ? "Hand over" : "Assign"}{to ? ` to ${to}` : ""}</Button>
          </div>
        </form>) : error ? null : <p className="ds-muted" role="status">Loading the project.</p>}
    </PageFrame>
  );
}
