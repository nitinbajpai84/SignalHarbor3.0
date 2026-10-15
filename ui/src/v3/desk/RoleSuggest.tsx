import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { apiGet, apiSend } from "../../api/client";
import { startThread } from "../api";
import "./roleSuggest.css";

export interface RoleBuild { id: string; title: string; say: string; dashboard: string; skills: string[]; started: string | null }
export interface RoleOption { id: string; title: string }
export interface MyRole { role: RoleOption | null; actions: string[]; builds: RoleBuild[]; roles: RoleOption[] }
export interface JobPerson { email: string; name: string; role: string | null }

export const getMyRole = () => apiGet<MyRole>("/api/v3/me/role");
export const getJobs = () => apiGet<{ people: JobPerson[]; roles: RoleOption[] }>("/api/v3/people/jobs");
export const setJob = (email: string, role: string) => apiSend<MyRole>("POST", "/api/v3/people/job", { email, role });

export default function RoleSuggest() {
  const nav = useNavigate();
  const [me, setMe] = useState<MyRole | null>(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => { getMyRole().then((r) => setMe(Array.isArray(r?.roles) ? r : null), () => setMe(null)); }, []);

  const start = useCallback(async (b: RoleBuild) => {
    if (b.started) return nav(`/v3/build/${b.started}`);
    setBusy(true);
    setErr("");
    try { nav(`/v3/build/${(await startThread(b.say)).id}`); } catch { setErr("Harbor could not start that. Try again."); setBusy(false); }
  }, [nav]);

  async function pick(role: string) {
    if (!role) return;
    setErr("");
    try { setMe(await setJob("", role)); } catch { setErr("Could not save your role. Try again."); }
  }

  if (!me || (!me.role && !me.roles.length)) return null; // no pack: nothing honest to suggest
  if (!me.role) {
    return (
      <section className="rs-card v3-card" aria-labelledby="rs-h0">
        <h2 id="rs-h0">Tell Harbor your role</h2>
        <p className="v3-mute">Harbor will suggest what you act on and what to build from it.</p>
        {err && <p className="v3-err" role="alert">{err}</p>}
        <label className="rs-pick">Your role
          <select value="" onChange={(e) => void pick(e.target.value)}>
            <option value="">Choose your role</option>
            {me.roles.map((r) => <option key={r.id} value={r.id}>{r.title}</option>)}
          </select>
        </label>
      </section>
    );
  }
  return (
    <section className="rs-card v3-card" aria-labelledby="rs-h">
      <h2 id="rs-h">For you, {me.role.title}</h2>
      {err && <p className="v3-err" role="alert">{err}</p>}
      <div className="rs-grid">
        <div>
          <p className="v3-label">What you act on</p>
          <ul>{me.actions.map((a) => <li key={a}>{a}</li>)}</ul>
        </div>
        <div>
          <p className="v3-label">Builds Harbor suggests</p>
          <ul className="rs-builds">
            {me.builds.map((b) => (
              <li key={b.id}>
                <div className="v3-row"><b>{b.title}</b><span className="v3-pill harbor">suggested</span></div>
                {b.dashboard && <small className="v3-mute">{b.dashboard}</small>}
                <div><button type="button" className="go" disabled={busy} onClick={() => void start(b)}>{b.started ? "Open" : "Start this"}</button></div>
              </li>))}
          </ul>
        </div>
      </div>
    </section>
  );
}
