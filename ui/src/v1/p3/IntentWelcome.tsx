import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { ApiError } from "../../api/client";
import Panel from "../../components/Panel";
import { Button, PageFrame } from "../../design";
import { useSession } from "../../useSession";
import ConversationPage from "../i6/ConversationPage";
import { getOpen, startChat } from "../i6/api";
import { getExample, getTemplate, listTemplates, type Example, type TemplateSummary } from "../t1/api";
import RequestBox from "../t1/RequestBox";
import TemplateCards from "../t1/TemplateCards";

// P3 + T1: /centre/intent. With an open conversation the person goes straight back to it; otherwise a welcome first: what North will
// ask (the chosen template's must-fill fields, then the good-to-have ones), what the person leaves with, the adopted templates to
// start from (default: the company's standard) and a first line to start with.

const LEAVE_WITH = [
  "An intent of work, which you sign",
  "A process map of how it is done today, by team",
  "The systems and files the work needs, who owns them and how often they arrive",
  "Business definitions of each figure",
  "A benchmark sheet to check the first load against",
];

const plain = (err: unknown) => (err instanceof ApiError && err.message ? err.message : "That did not go through. Please try again.");

export default function IntentWelcome() {
  const nav = useNavigate();
  const fresh = useSearchParams()[0].get("new") === "1";  // "Start a new intent" on the conversation page comes here and stays here
  const first = (useSession().user?.display_name ?? "").split(" ")[0];
  const [state, setState] = useState<"looking" | "welcome" | "chat">("looking");
  const [templates, setTemplates] = useState<TemplateSummary[]>([]);
  const [pick, setPick] = useState("");
  const [example, setExample] = useState<Example | null>(null);
  const [recent, setRecent] = useState<{ id: string; title: string; state: string }[]>([]);
  const [labels, setLabels] = useState<Record<string, string>>({});
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [answer, setAnswer] = useState("");  // North answered a question without starting an intent

  useEffect(() => {
    let live = true;
    getOpen()
      .then((o) => { if (!live) return; setRecent(o.recent ?? []); if (o.id && !fresh) nav(`/centre/intent/${encodeURIComponent(o.id)}`, { replace: true }); else setState("welcome"); })
      .catch(() => { if (live) setState("welcome"); });
    listTemplates("intent_of_work")
      .then((all) => { if (live && Array.isArray(all)) { setTemplates(all); setPick((all.find((t) => t.standard) ?? all[0])?.id ?? ""); } })
      .catch(() => undefined); // the welcome works without the templates
    return () => { live = false; };
  }, [nav, fresh]);

  async function start() {
    if (!text.trim()) { setState("chat"); return; }
    setBusy(true);
    setError("");
    try {
      const made = await startChat(text.trim(), [], pick || undefined);
      const iid = made.id || made.intent_id;
      if (iid) nav(`/centre/intent/${encodeURIComponent(iid)}`);
      else setAnswer(made.turns?.filter((t) => t.by === "north").at(-1)?.text ?? "North answered without starting an intent.");
    } catch (err) {
      setError(plain(err));
    } finally {
      setBusy(false);
    }
  }

  if (state === "chat") return <ConversationPage />;
  if (state === "looking") return <PageFrame title="Intent Centre"><p className="ds-muted" role="status">Opening the Intent Centre…</p></PageFrame>;

  const openExample = (eid: string, tid: string) => Promise.all([getExample(eid), getTemplate(tid)])
    .then(([ex, t]) => { setLabels({ ...Object.fromEntries(t.fields.map((f) => [f.key, f.label])), comments: t.free_text.label }); setExample(ex); })
    .catch(() => undefined);
  const chosen = templates.find((t) => t.id === pick);
  return (
    <PageFrame title={`Hi${first ? ` ${first}` : ""}. What are you planning to build today?`}
      subline="North, our industry expert, will talk it through with you and write the intent of work as you go.">
      <Panel title="What do you need?">
        <p className="ds-muted" style={{ marginTop: 0 }}>Describe the report, check or process in your own words. North takes it from there.</p>
        <form onSubmit={(ev) => { ev.preventDefault(); void start(); }} style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <textarea className="ds-input" aria-label="What you would like to build" rows={3}
            placeholder="For example: a monthly report of fund performance by entity, net of fees, for the investment committee by the 8th working day"
            value={text} onChange={(ev) => setText(ev.target.value)} style={{ flex: "1 1 320px" }} />
          <Button variant="primary" type="submit" disabled={busy}>{busy ? "Starting…" : "Start"}</Button>
        </form>
        {error ? <p role="alert">{error}</p> : null}
        {answer ? <p role="status"><b>North:</b> {answer}</p> : null}
      </Panel>
      {recent.length ? (
        <Panel title="Your recent intents">
          <ul>{recent.map((r) => <li key={r.id}><Link className="ds-link" to={`/centre/intent/${encodeURIComponent(r.id)}`}>{r.title}</Link>{" "}<span className="ds-muted">{r.state}</span></li>)}</ul>
        </Panel>
      ) : null}
      <Panel title="Around your intents">
        <p><Link className="ds-link" to="/centre/intent/graph">Company map</Link> · <Link className="ds-link" to="/centre/intent/backlog">Backlog</Link> · <Link className="ds-link" to="/centre/intent/past">Past intents</Link></p>
      </Panel>
      <Panel title="What North will ask you">
        <p className="ds-muted" style={{ marginTop: 0 }}>In your own words; North reads what it can from your files and suggests the rest.</p>
        {chosen ? (
          <>
            <ol>{chosen.required.map((c) => <li key={c}>{c}</li>)}</ol>
            {chosen.good_to_have.length ? (
              <>
                <p className="ds-muted">If there is time, and only if they apply:</p>
                <ul>{chosen.good_to_have.map((c) => <li key={c}>{c}</li>)}</ul>
              </>
            ) : null}
          </>
        ) : <p className="ds-muted">North will start with what you want to build and why, and take it from there.</p>}
      </Panel>
      <Panel title="What you will leave with">
        <ul>{LEAVE_WITH.map((c) => <li key={c}>{c}</li>)}</ul>
      </Panel>
      <Panel title="Start from a template">
        <p className="ds-muted" style={{ marginTop: 0 }}>The intent of work, the process map and the definitions open laid out like this, and North fills them in as you talk.</p>
        <TemplateCards templates={templates} pick={pick} onPick={setPick}
          extra={(t) => t.examples.map((x) => <Button key={x.id} onClick={() => openExample(x.id, t.id)}>Example: {x.name}</Button>)} />
        {example ? (
          <div aria-label="Example">
            <h3>{example.name}</h3>
            <dl>{Object.entries(example.values).filter(([, v]) => (Array.isArray(v) ? v.length : v)).map(([k, v]) => (
              <div key={k}><dt className="ds-muted">{labels[k] ?? k}</dt><dd>{Array.isArray(v) ? v.join("; ") : v}</dd></div>
            ))}</dl>
          </div>
        ) : null}
        <RequestBox about="intent of work" />
      </Panel>
    </PageFrame>
  );
}
