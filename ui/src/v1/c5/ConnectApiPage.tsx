import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError } from "../../api/client";
import { PageFrame } from "../../design";
import { listApiProviders, saveApi, testApi, type ApiProvider, type ApiTest } from "./api";

// Build, Connect an API. Outside figures on a schedule from a fixed list of providers; the key is named, never shown or typed.
const field = { display: "grid", gap: 6, fontSize: 13 } as const;
const box = { padding: 11, borderRadius: 10, font: "inherit", fontSize: 14 } as const;
const plain = (err: unknown) => (err instanceof ApiError && err.message ? err.message : "That did not go through. Please try again.");

export default function ConnectApiPage() {
  const [providers, setProviders] = useState<ApiProvider[] | null>(null);
  const [pid, setPid] = useState("");
  const [picked, setPicked] = useState<string[]>([]);
  const [result, setResult] = useState<ApiTest | null>(null);
  const [saved, setSaved] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    listApiProviders().then((r) => { setProviders(r.providers); setPid(r.providers[0]?.id ?? ""); setPicked(r.providers[0]?.series.slice(0, 2).map((s) => s.id) ?? []); }).catch((e) => { setProviders([]); setError(plain(e)); });
  }, []);
  const p = providers?.find((x) => x.id === pid);
  const choose = (id: string) => { const n = providers?.find((x) => x.id === id); setPid(id); setPicked(n?.series.slice(0, 2).map((s) => s.id) ?? []); setResult(null); setSaved(""); };
  const toggle = (id: string) => { setPicked(picked.includes(id) ? picked.filter((x) => x !== id) : [...picked, id]); setResult(null); setSaved(""); };
  const run = async (fn: () => Promise<void>) => { setBusy(true); setError(""); try { await fn(); } catch (e) { setError(plain(e)); } finally { setBusy(false); } };
  const test = () => run(async () => { setResult(await testApi(pid, picked)); });
  const save = () => run(async () => { await saveApi(pid, picked); setSaved(`Saved. ${p?.name ?? "The provider"} will be pulled every day at 05:30, before the 06:00 run.`); });

  const aside = (
    <>
      <section aria-label="Test result" className="ds-card" style={{ display: "grid", gap: 8, padding: 16, minWidth: 0, overflowWrap: "anywhere" }}>
        <h2 style={{ margin: 0, fontSize: 16 }}>Test result</h2>
        {result === null ? <p className="ds-muted">Press Test the connection to see real values before anything is saved.</p> : (
          <>
            <p role="status">{result.message}</p>
            {result.ok && result.rows ? (
              <div role="table" aria-label="Series, date, value" style={{ display: "grid", gridTemplateColumns: "1fr auto auto", gap: "6px 12px", fontSize: 13, fontFamily: "'IBM Plex Mono', monospace" }}>
                <span role="columnheader" className="ds-muted">Series</span><span role="columnheader" className="ds-muted">Date</span><span role="columnheader" className="ds-muted">Value</span>
                {result.rows.map((r) => <span key={r.series} style={{ display: "contents" }} role="row"><span role="cell">{r.series}</span><span role="cell">{r.date}</span><span role="cell">{r.value}</span></span>)}
              </div>) : null}
            {result.ok && result.headlines?.length ? <ul>{result.headlines.map((h) => <li key={h}>{h}</li>)}</ul> : null}
          </>)}
        <p className="ds-muted">Lands in market observations, marked outside, with this provider as the source. It shows in Consume › Markets. News goes to “To watch” and is never a figure.</p>
      </section>
      <section className="ds-card" style={{ padding: 16, minWidth: 0 }}>
        <strong>Safe by design.</strong> The address is added to the office&apos;s allowed list, every call is logged, and the key never appears on screen. Internet access is off until an administrator switches it on. Only the series asked for are sent: nothing about the office.
      </section>
    </>);

  return (
    <PageFrame title="Connect an API" crumbs={<Link className="ds-link" to="/centre/data/intake">All sources</Link>} aside={aside}
      subline="Pull outside figures (exchange rates, index levels, yields, news) on a schedule. Nothing about the office is sent: only the series asked for.">
      {error ? <p role="alert">{error}</p> : null}
      {providers === null ? <p className="ds-muted" role="status">Loading the providers.</p> : (
        <form onSubmit={(e) => e.preventDefault()} style={{ display: "grid", gap: 10, maxWidth: 620 }}>
          <label style={field}>Provider
            <select style={box} value={pid} onChange={(e) => choose(e.target.value)}>
              {providers.map((x) => <option key={x.id} value={x.id}>{x.name} · {x.blurb}</option>)}
            </select></label>
          <label style={field}>Key, if the provider needs one
            <input style={{ ...box, background: "transparent", opacity: 0.8 }} disabled readOnly aria-label="Key" value={p?.needs_key ? `Stored by the administrator as ${p.key_env}` : "No key needed"} /></label>
          {p?.needs_key ? <p className={p.key_set ? "ds-muted" : undefined} role="note">{p.key_set ? `${p.key_env} is set on the server.` : `${p.key_env} is not set on the server yet. Ask the administrator to store it under that name.`}</p> : null}
          <fieldset><legend>What to pull</legend>
            {p?.series.map((s) => (
              <label key={s.id} style={{ display: "block" }}><input type="checkbox" checked={picked.includes(s.id)} onChange={() => toggle(s.id)} /> {s.id}: {s.label}</label>))}
          </fieldset>
          <label style={field}>When
            <select style={box} aria-label="When" defaultValue="daily"><option value="daily">Daily at 05:30, before the 06:00 run</option></select></label>
          <div style={{ display: "flex", gap: 10 }}>
            <button className="ds-btn" type="button" disabled={busy || !picked.length} onClick={() => void test()}>Test the connection</button>
            <button className="ds-btn" type="button" disabled={busy || !picked.length} onClick={() => void save()}>Save</button>
          </div>
          {saved ? <p role="status">{saved}</p> : null}
        </form>)}
    </PageFrame>
  );
}
