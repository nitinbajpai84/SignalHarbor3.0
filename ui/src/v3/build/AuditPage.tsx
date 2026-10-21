import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError, apiGet, apiSend, downloadFile } from "../../api/client";
import V3Frame from "../Frame";
import "./build.css";

interface Entry { seq: number; ts: string; actor: string; action: string; detail: string; ok: boolean; hash: string }
interface AuditOut { entries: Entry[]; total: number; chain: { ok: boolean; count: number; broken_at: number | null } }
interface Sec { mfa_required: boolean; people: number; mfa_enrolled: number }
const ACTIONS = ["login", "login_failed", "logout", "read", "export", "change", "settings_change", "signed_decision", "audit_view"];

/** Build > Audit log (company admin): every sign-in, read, export, change and signed decision, chain-checked, with a CSV export and the MFA setting. */
export default function AuditPage() {
  const [f, setF] = useState({ actor: "", action: "", q: "" });
  const [out, setOut] = useState<AuditOut | null>(null);
  const [sec, setSec] = useState<Sec | null>(null);
  const [err, setErr] = useState("");
  const qs = useCallback(() => new URLSearchParams(Object.entries(f).filter(([, v]) => v)).toString(), [f]);
  const load = useCallback(() => {
    apiGet<AuditOut>(`/api/v3/audit?${qs()}`).then((o) => { setOut(o); setErr(""); }).catch((e: Error) => setErr(e.message || "Could not load the audit log"));
  }, [qs]);
  useEffect(load, [load]);
  useEffect(() => { apiGet<Sec>("/api/v3/security/settings").then(setSec).catch(() => undefined); }, []);
  const mfa = async (on: boolean) => {
    try { setSec(await apiSend<Sec>("PUT", "/api/v3/security/settings", { mfa_required: on })); } catch (e) { setErr((e as Error).message); }
  };
  const csv = () => downloadFile(`/api/v3/audit/export.csv?${qs()}`, "audit-log.csv").catch((e: ApiError) => setErr(e.message));
  return (
    <V3Frame back={<Link to="/v3/build" className="b3-back">&larr; Use cases</Link>}>
      <main className="b3-board b3">
        <div><h1>Audit log</h1>
          <p className="v3-mute">Who signed in, what they read, exported, changed and signed. Entries cannot be edited; each is chained to the one before.</p></div>
        {err && <p className="v3-err" role="alert">{err}</p>}
        {sec && <section className="v3-card"><h2>Second step at sign-in</h2>
          <label><input type="checkbox" checked={sec.mfa_required} onChange={(e) => void mfa(e.target.checked)} /> Everyone in this office must use an authenticator app</label>
          <p className="v3-mute">{sec.mfa_enrolled} of {sec.people} people have set it up. Anyone who has not is asked to set it up at their next sign-in.</p></section>}
        <section className="v3-card">
          <div className="v3-row" role="search">
            <input aria-label="Person" placeholder="Person" value={f.actor} onChange={(e) => setF({ ...f, actor: e.target.value })} />
            <select aria-label="What they did" value={f.action} onChange={(e) => setF({ ...f, action: e.target.value })}>
              <option value="">Everything</option>{ACTIONS.map((a) => <option key={a} value={a}>{a.replace("_", " ")}</option>)}
            </select>
            <input aria-label="Contains" placeholder="Contains" value={f.q} onChange={(e) => setF({ ...f, q: e.target.value })} />
            <button onClick={() => void csv()}>Download CSV</button>
          </div>
          {out && <p className="v3-mute" role="status">{out.chain.ok ? `Chain intact (${out.chain.count} entries).` : `Chain broken at entry ${out.chain.broken_at}: the log was changed.`} Showing {out.entries.length} of {out.total}.</p>}
          {out && out.entries.length === 0 && <p className="v3-mute">Nothing matches.</p>}
          {out?.entries.map((e) => (
            <div key={e.seq} className="v3-row"><span style={{ minWidth: 150 }}>{e.ts.replace("T", " ").replace("+00:00", "Z")}</span>
              <b style={{ minWidth: 160 }}>{e.actor}</b><span style={{ minWidth: 120 }}>{e.action.replace("_", " ")}{e.ok ? "" : " (refused)"}</span><span className="v3-mute">{e.detail}</span></div>))}
        </section>
      </main>
    </V3Frame>
  );
}
