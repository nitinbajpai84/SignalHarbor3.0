import { useCallback, useEffect, useState } from "react";

import { ApiError, apiGet, apiSend } from "../../api/client";
import { Button } from "../../design";

// W2 MCP: Settings, outside assistants. A token lets an assistant you choose (Claude, Cursor) read what you may read. Shown once; only a hash is kept.
interface Tok { id: string; label: string; scopes: string[]; created: string; expires: string; revoked: boolean; last_used: string | null; active: boolean }
interface Listing { tokens: Tok[]; scopes: string[] }
const plain = (e: unknown) => (e instanceof ApiError && e.message ? e.message : "That did not go through. Please try again.");
const SCOPE_WORDS: Record<string, string> = { read: "Read figures and answers", propose: "Propose drafts for your yes", export: "Export reports" };

export default function McpTokens() {
  const [d, setD] = useState<Listing | null>(null);
  const [err, setErr] = useState("");
  const [label, setLabel] = useState("");
  const [scopes, setScopes] = useState<string[]>(["read"]);
  const [days, setDays] = useState(30);
  const [shown, setShown] = useState("");
  const load = useCallback(() => { apiGet<Listing>("/api/v1/mcp/tokens").then((r) => { setD(r); setErr(""); }, (e) => setErr(plain(e))); }, []);
  useEffect(() => { load(); }, [load]);
  const issue = async () => {
    try { const r = await apiSend<{ token: string }>("POST", "/api/v1/mcp/tokens", { label, scopes, days }); setShown(r.token); setLabel(""); load(); } catch (e) { setErr(plain(e)); }
  };
  const revoke = async (id: string) => { try { await apiSend("DELETE", `/api/v1/mcp/tokens/${encodeURIComponent(id)}`); load(); } catch (e) { setErr(plain(e)); } };
  const live = (d?.tokens ?? []).filter((t) => t.active);
  return (
    <section aria-label="Outside assistants" style={{ display: "grid", gap: 12 }}>
      <h2 style={{ margin: 0 }}>Outside assistants</h2>
      <p className="ds-muted">Give an assistant you choose a token and it can ask Signal Harbor for figures and answers as you, never more than you may see. It leaves your company space, so issue one only for a tool you trust.</p>
      {err ? <p role="alert" className="ds-warn">{err}</p> : null}
      {shown ? <p role="status" className="ds-card" style={{ padding: 12, margin: 0, overflowWrap: "anywhere" }}>Copy this token now; it is not shown again: <code>{shown}</code></p> : null}
      <form className="ds-card" style={{ padding: 16, display: "grid", gap: 12 }} onSubmit={(e) => { e.preventDefault(); if (label.trim() && scopes.length) void issue(); }}>
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "end" }}>
          <label style={{ display: "grid", gap: 4, flex: "1 1 260px" }}>Name <input className="ds-input" value={label} onChange={(e) => setLabel(e.target.value)} placeholder="For example Claude on my laptop" /></label>
          <label style={{ display: "grid", gap: 4 }}>Days <input className="ds-input" type="number" min={1} max={365} value={days} onChange={(e) => setDays(Number(e.target.value))} style={{ width: 90 }} /></label>
        </div>
        <fieldset style={{ border: 0, padding: 0, margin: 0, display: "flex", gap: 16, flexWrap: "wrap" }}>
          <legend className="ds-footnote" style={{ padding: 0, marginBottom: 6 }}>What it may do</legend>
          {(d?.scopes ?? ["read"]).map((s) => (
            <label key={s} style={{ display: "flex", gap: 8, alignItems: "center" }}><input type="checkbox" checked={scopes.includes(s)} onChange={(e) => setScopes(e.target.checked ? [...scopes, s] : scopes.filter((x) => x !== s))} /> {SCOPE_WORDS[s] ?? s}</label>
          ))}
        </fieldset>
        <div><Button type="submit" variant="primary" disabled={!label.trim() || !scopes.length}>Issue token</Button></div>
      </form>
      {d && !live.length ? <p className="ds-muted">No active tokens.</p> : (
        <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "grid", gap: 8 }}>
          {live.map((t) => (
            <li key={t.id} className="ds-card" style={{ padding: 12, display: "flex", gap: 12, justifyContent: "space-between", alignItems: "center", flexWrap: "wrap" }}>
              <span><strong>{t.label}</strong> <span className="ds-muted">({t.scopes.join(", ")}; expires {t.expires.slice(0, 10)}; {t.last_used ? `last used ${t.last_used.slice(0, 10)}` : "not used yet"})</span></span>
              <Button onClick={() => void revoke(t.id)}>Revoke</Button></li>
          ))}
        </ul>
      )}
    </section>
  );
}
