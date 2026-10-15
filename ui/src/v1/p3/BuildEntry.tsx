import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { ApiError, apiGet, apiSend } from "../../api/client";
import Panel from "../../components/Panel";
import { Button, EmptyState, PageFrame, Pill } from "../../design";

// P3: /centre/build. The signed intents of work nobody has picked up yet, and the work already in build
// (sh_platform/v1/p3_routes.py). Picking one up records the builder and opens Span's design conversation.

interface Line { intent_id: string; title: string; pid: string | null }
export interface Waiting {
  waiting: (Line & { signed_by: string | null; signed_at: string | null })[];
  in_build: (Line & { builder: string; stage: string })[];
}

const day = (at: string | null) => {
  const d = new Date(at ?? "");
  return Number.isNaN(d.getTime()) ? "" : d.toLocaleDateString("en-GB", { dateStyle: "medium" });
};
const plain = (err: unknown) => (err instanceof ApiError && err.message ? err.message : "That did not go through. Please try again.");
const at = (iid: string) => `/centre/build/${encodeURIComponent(iid)}`;

export default function BuildEntry() {
  const nav = useNavigate();
  const [data, setData] = useState<Waiting | null>(null);
  const [failed, setFailed] = useState(false);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(() => apiGet<Waiting>("/api/v1/build/waiting").then((d) => { setData(d); setFailed(false); }, () => setFailed(true)), []);
  useEffect(() => { void load(); }, [load]);

  async function pick(iid: string) {
    setBusy(iid);
    setError("");
    try {
      await apiSend("POST", `/api/v1/build/pickup/${encodeURIComponent(iid)}`);
      nav(at(iid));
    } catch (err) {
      setError(plain(err));
      void load();
    } finally {
      setBusy("");
    }
  }

  return (
    <PageFrame title="Ready to build something?"
      subline="Each piece of work is built in two rooms. In Design, Span, the build agent, drafts the system design and the mapping from the signed intent of work. In Pipeline, Span, the build agent, loads the data from that mapping and checks the figures.">
      {failed ? <p role="alert">The work list could not be read. <Button onClick={() => void load()}>Try again</Button></p>
        : !data ? <p className="ds-muted" role="status">Reading the work list…</p>
        : <>
          {error ? <p role="alert">{error}</p> : null}
          <Panel title="Waiting for a builder">
            {data.waiting.length === 0
              ? <EmptyState title="Nothing is waiting" lines={["A signed intent of work appears here until someone picks it up."]} />
              : data.waiting.map((w) => (
                <div key={w.intent_id} style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap", margin: "8px 0" }}>
                  <strong style={{ flex: "1 1 240px" }}>{w.title}</strong>
                  {w.signed_by ? <span className="ds-muted">Signed by {w.signed_by}{w.signed_at ? `, ${day(w.signed_at)}` : ""}</span> : null}
                  <Button variant="primary" disabled={busy === w.intent_id} onClick={() => void pick(w.intent_id)}
                    aria-label={`Pick up ${w.title}`}>Pick one up</Button>
                </div>
              ))}
          </Panel>
          <Panel title="Already in build">
            {data.in_build.length === 0
              ? <p className="ds-muted">Nothing is in build yet.</p>
              : data.in_build.map((b) => (
                <div key={b.intent_id} style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap", margin: "8px 0" }}>
                  <strong style={{ flex: "1 1 240px" }}>{b.title}</strong>
                  <span className="ds-muted">Builder: {b.builder}</span>
                  <Pill tone="draft">{b.stage.charAt(0).toUpperCase() + b.stage.slice(1)}</Pill>
                  <Link className="ds-link" to={at(b.intent_id)}>Design</Link>
                  <Link className="ds-link" to={`${at(b.intent_id)}/engineer`}>Pipeline</Link>
                </div>
              ))}
          </Panel>
        </>}
    </PageFrame>
  );
}
