import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import {
  clearApiWebhook, listApiKeys, makeApiKey, revokeApiKey, setApiWebhook,
  type ApiCall, type ApiKey, type ApiKeyMade, type ApiScope,
} from "../api";
import V3Frame from "../Frame";
import "./build.css";

const SCOPE_WORDS: Record<ApiScope, string> = {
  figures: "Figures and their receipts", ask: "Ask a question", signals: "Signals that fired", documents: "Document list (never the files)",
};
const ALL: ApiScope[] = ["figures", "ask", "signals", "documents"];

/** The API keys page under Build: an office admin makes and revokes the keys a client's own tools use to read Consume. A key is shown once. */
export default function ApiKeys() {
  const [keys, setKeys] = useState<ApiKey[] | null>(null);
  const [calls, setCalls] = useState<ApiCall[]>([]);
  const [err, setErr] = useState("");
  const [made, setMade] = useState<ApiKeyMade | null>(null);
  const [hook, setHook] = useState<{ id: string; secret: string; allowed: boolean } | null>(null);
  const [label, setLabel] = useState("");
  const [scopes, setScopes] = useState<ApiScope[]>(["figures"]);
  const [family, setFamily] = useState(false);
  const [member, setMember] = useState("");
  const [entities, setEntities] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    listApiKeys().then((r) => { setKeys(r.keys); setCalls(r.calls); setErr(""); }).catch((e: Error) => setErr(e.message));
  }, []);
  useEffect(() => { load(); }, [load]);

  const act = async (go: () => Promise<void>) => {
    setBusy(true); setErr("");
    try { await go(); load(); } catch (e) { setErr((e as Error).message || "That did not work. Please try again."); } finally { setBusy(false); }
  };
  const ids = entities.split(",").map((s) => s.trim()).filter(Boolean);
  const toggle = (s: ApiScope) => setScopes(scopes.includes(s) ? scopes.filter((x) => x !== s) : [...scopes, s]);
  const create = () => act(async () => {
    setMade(await makeApiKey({ label, scopes, kind: family ? "family" : "company", member: family ? member : undefined, entity_ids: ids.length ? ids : undefined }));
    setLabel(""); setEntities(""); setMember("");
  });
  const live = (keys ?? []).filter((k) => !k.revoked);

  return (
    <V3Frame back={<Link to="/v3/build">&larr; Build</Link>}>
      <main className="b3-board b3">
        <div>
          <h1>API keys</h1>
          <p className="v3-mute">A key lets your own tools read this office's figures, signals and document list, and ask questions. It can only read. Each call is logged.</p>
        </div>
        {err && <p className="v3-err" role="alert">{err} <button onClick={load}>Try again</button></p>}
        {made && (
          <section className="v3-card" aria-label="New key" role="status">
            <h2 style={{ fontSize: 18 }}>Copy this key now</h2>
            <p className="v3-mute">It is shown once and cannot be shown again. If it is lost, revoke it and make a new one.</p>
            <code style={{ wordBreak: "break-all", userSelect: "all" }}>{made.key}</code>
            <div className="v3-row"><button className="go" onClick={() => void navigator.clipboard?.writeText(made.key)}>Copy</button><button onClick={() => setMade(null)}>Done</button></div>
          </section>
        )}
        <form className="v3-card" onSubmit={(e) => { e.preventDefault(); void create(); }} aria-label="Make a key">
          <h2 style={{ fontSize: 18 }}>Make a key</h2>
          <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>Name (the tool it is for)
            <input value={label} onChange={(e) => setLabel(e.target.value)} maxLength={60} />
          </label>
          <fieldset style={{ border: 0, padding: 0 }}>
            <legend className="v3-mute">What it may read</legend>
            {ALL.map((s) => (
              <label key={s} style={{ display: "block" }}><input type="checkbox" checked={scopes.includes(s)} onChange={() => toggle(s)} /> {SCOPE_WORDS[s]}</label>
            ))}
          </fieldset>
          <label style={{ display: "block" }}>
            <input type="checkbox" checked={family} onChange={() => { setFamily(!family); setScopes(scopes.filter((s) => s !== "ask")); }} /> This key is for a family member (sees only their own share)
          </label>
          {family && (
            <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>Family member
              <input value={member} onChange={(e) => setMember(e.target.value)} />
            </label>
          )}
          <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            Only these entities (optional, separated by commas{family ? "; left empty, Harbor uses the member's signed access" : ""})
            <input value={entities} onChange={(e) => setEntities(e.target.value)} />
          </label>
          {(ids.length > 0 || family) && scopes.includes("ask") && <small className="v3-mute">A key limited to some entities cannot ask: an answer is worked out over the whole office.</small>}
          <div className="v3-row">
            <button type="submit" className="go" disabled={busy || !label.trim() || scopes.length === 0 || (family && !member.trim() && ids.length === 0)}>Make the key</button>
          </div>
        </form>

        {keys === null && !err && <p className="v3-mute" role="status">Loading keys...</p>}
        {keys !== null && live.length === 0 && <p className="v3-mute">No key yet.</p>}
        {live.map((k) => (
          <article key={k.id} className="v3-card" aria-label={k.label}>
            <b>{k.label}</b> <span className="v3-pill info">{k.kind === "family" ? `Family: ${k.member ?? ""}` : "Whole office"}</span>
            <p className="v3-mute">{k.scopes.map((s) => SCOPE_WORDS[s]).join(", ")}{k.entity_ids.length ? `; entities ${k.entity_ids.join(", ")}` : ""}; up to {k.rate_per_min} calls a minute.</p>
            <p className="v3-mute">Made {k.created.slice(0, 10)}{k.created_by ? ` by ${k.created_by}` : ""}. {k.webhook ? `Webhook: ${k.webhook.url}` : ""}</p>
            {hook?.id === k.id && (
              <p role="status">Signing secret (shown once): <code style={{ userSelect: "all" }}>{hook.secret}</code>{hook.allowed ? "" : " Add the address's host to the webhook list in Settings, or nothing will be sent."}</p>
            )}
            <div className="v3-row">
              {k.scopes.includes("signals") && (
                <button disabled={busy} onClick={() => {
                  const url = window.prompt("Where should Harbor send \"signal fired\"? (an https address)", k.webhook?.url ?? "");
                  if (url) void act(async () => { const r = await setApiWebhook(k.id, url); setHook({ id: k.id, secret: r.secret, allowed: r.allowed }); });
                }}>{k.webhook ? "Change webhook" : "Add webhook"}</button>
              )}
              {k.webhook && <button disabled={busy} onClick={() => void act(async () => { await clearApiWebhook(k.id); setHook(null); })}>Remove webhook</button>}
              <button disabled={busy} onClick={() => { if (window.confirm(`Revoke "${k.label}"? Tools using it stop working at once.`)) void act(async () => { await revokeApiKey(k.id); }); }}>Revoke</button>
            </div>
          </article>
        ))}

        {calls.length > 0 && (
          <section aria-label="Recent calls">
            <h2 style={{ fontSize: 18 }}>Recent calls</h2>
            <table>
              <thead><tr><th>When</th><th>Key</th><th>Call</th><th>Result</th></tr></thead>
              <tbody>{calls.map((c, i) => (
                <tr key={i}><td>{c.at.replace("T", " ").replace("Z", "")}</td><td>{keys?.find((k) => k.id === c.key)?.label ?? c.key}</td><td>{c.route}</td><td>{c.status}</td></tr>
              ))}</tbody>
            </table>
          </section>
        )}
      </main>
    </V3Frame>
  );
}
