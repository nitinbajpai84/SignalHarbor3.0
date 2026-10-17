import { useEffect, useState } from "react";

import { getPeople, setAutonomy, type Level, type People } from "../api";
import { getJobs, setJob, type JobPerson, type RoleOption } from "../desk/RoleSuggest";
import { useThreadTitles } from "../plain";
import { TrustPage, useLoad } from "./b/Shell";

const LEVELS: [Level, string][] = [["assist", "Assist"], ["auto", "Auto"], ["silent", "Silent"]];
const ROLES = [["decides", "Decides"], ["does", "Does"], ["reads", "Reads"]] as const;

export default function PeoplePage() {
  const s = useLoad<People>(getPeople, "people");
  const [msg, setMsg] = useState("");
  const p = s.data;
  const title = useThreadTitles();
  const [jobs, setJobs] = useState<JobPerson[]>([]);
  const [roles, setRoles] = useState<RoleOption[]>([]);
  useEffect(() => { getJobs().then((j) => { setJobs(Array.isArray(j.people) ? j.people.filter((x) => x.email) : []); setRoles(Array.isArray(j.roles) ? j.roles : []); }, () => undefined); }, []);
  const job = async (x: JobPerson, role: string) => {
    setMsg("");
    try { await setJob(x.email, role); setJobs((l) => l.map((y) => (y.email === x.email ? { ...y, role: role || null } : y))); } catch (e) { setMsg((e as Error).message || "Could not save"); }
  };
  const pick = async (thread: string, level: Level) => {
    setMsg("");
    try { s.set(await setAutonomy(thread, level)); } catch (e) { setMsg((e as Error).message || "Could not save"); }
  };
  const none = !!p && !p.people.length && !p.autonomy.length && !p.ask_rules.length;
  return (
    <TrustPage kicker="Trust › People and rules" title="Who decides, what Harbor does alone, and when it asks" state={s} empty={none ? "No people have been added yet." : false}>
      {p && <>
        {msg && <p className="v3-err" role="alert">{msg}</p>}
        <section className="v3-card"><h2>People</h2>
          <p className="v3-mute">Decides signs off a thread. Does runs it. Reads sees the output.</p>
          {p.people.map((x) => (
            <div key={x.name} className="v3-row" role="group" aria-label={x.name}>
              <b style={{ minWidth: 120 }}>{x.name}</b>
              {ROLES.map(([r, l]) => (
                <span key={r} className="v3-chips"><span className={x.role === r ? "tr-on" : undefined}>{l}</span></span>
              ))}
            </div>))}
          {roles.length > 0 && <>
            <h3>Job</h3>
            <p className="v3-mute">Harbor suggests actions and builds for each job. The person can change it.</p>
            {jobs.map((x) => (
              <div key={x.email} className="v3-row">
                <label style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}><b style={{ minWidth: 120 }}>{x.name}</b>
                  <select aria-label={`Job for ${x.name}`} value={x.role ?? ""} onChange={(e) => void job(x, e.target.value)}>
                    <option value="">No job set</option>
                    {roles.map((r) => <option key={r.id} value={r.id}>{r.title}</option>)}
                  </select>
                </label>
              </div>))}
          </>}
          <p className="v3-mute">Second signer for go live: {p.second_signer ? "On" : "Off"}</p>
        </section>
        <section className="v3-card"><h2>When Harbor must ask a person</h2>
          {p.ask_rules.map((r) => (
            <div key={r.id} className="v3-row">
              <span style={{ flex: 1 }}>{r.text}{r.value !== undefined ? ` (${r.value})` : ""}</span>
              <span className="v3-pill info">{r.on ? "On" : "Off"}</span>
            </div>))}
        </section>
        <section className="v3-card"><h2>Autonomy per thread</h2>
          {p.autonomy.map((a) => (
            <div key={a.thread} className="v3-row" role="group" aria-label={`Autonomy for ${title(a.thread)}`}>
              <b style={{ minWidth: 140 }} title={a.thread}>{title(a.thread)}</b>
              {LEVELS.map(([l, label]) => (
                <button key={l} className={a.level === l ? "go" : ""} aria-pressed={a.level === l} onClick={() => pick(a.thread, l)}>{label}</button>
              ))}
            </div>))}
          <p className="v3-mute">Steps up after two clean months, steps down after an unexplained break.</p>
        </section>
        <section className="v3-card"><h2>AI usage and cost</h2>
          <div className="v3-figs">
            <div className="v3-fig"><small>Questions asked</small><span className="num">{p.usage.questions}</span></div>
            <div className="v3-fig"><small>Builds run</small><span className="num">{p.usage.builds}</span></div>
            <div className="v3-fig"><small>Mode</small><span className="num">{p.usage.mode === "real" ? "Real" : "Testing"}</span></div>
          </div>
          <p className="v3-mute">Testing uses sample data. Only an admin can switch to Real.</p>
        </section>
      </>}
    </TrustPage>
  );
}
