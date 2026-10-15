import { useCallback, useEffect, useState, type ReactNode } from "react";
import { Link, useParams } from "react-router-dom";

import { ApiError } from "../../api/client";
import ScreenState from "../../components/ScreenState";
import { Button, PageFrame, Pill, SideCard, Signature } from "../../design";
import { download, editLine, getSow, sendBack, signSow, type LineEdit, type SowView } from "./api";

// I4: /centre/intent/:iid/sow. The eight sections, a line edited in place while draft, an unclear point settled, one signature
// with a confirm sentence (the charter's sign dialog, 2.0 ui/src/intents/views/CharterView.tsx SignModal), send back, download.

const said = (e: unknown) => (e instanceof ApiError && e.message ? e.message : "That did not work. Please try again.");
const list = (xs: string[] | undefined) => (xs && xs.length ? xs.join(", ") : "Not stated");
const day = (at: string) => new Date(at).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" });

function Line({ label, value, edit, can, save, area }: {
  label?: string; value: string; edit: Omit<LineEdit, "value">; can: boolean; save: (e: LineEdit) => Promise<void>; area?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState(value);
  if (!open) {
    return (
      <p style={{ margin: "4px 0" }}>
        {label ? <span className="ds-muted">{label}: </span> : null}{value || <span className="ds-muted">Not stated</span>}
        {can ? <> <button type="button" className="ds-link" onClick={() => { setText(value); setOpen(true); }} aria-label={`Edit ${label ?? "line"}`}>Edit</button></> : null}
      </p>
    );
  }
  const Input = area ? "textarea" : "input";
  return (
    <form style={{ display: "flex", gap: 8, flexWrap: "wrap", margin: "4px 0" }} onSubmit={(ev) => { ev.preventDefault(); void save({ ...edit, value: text }).then(() => setOpen(false)); }}>
      <Input className="ds-input" aria-label={label ?? "Line"} value={text} onChange={(ev) => setText(ev.target.value)} style={{ flex: "1 1 240px" }} />
      <Button variant="primary" type="submit">Save</Button>
      <Button onClick={() => setOpen(false)}>Cancel</Button>
    </form>
  );
}

function Settle({ question, save }: { question: string; save: (answer: string) => Promise<void> }) {
  const [text, setText] = useState("");
  return (
    <form style={{ display: "flex", gap: 8, flexWrap: "wrap" }} onSubmit={(ev) => { ev.preventDefault(); if (text.trim()) void save(text); }}>
      <input className="ds-input" aria-label={`Answer: ${question}`} placeholder="The answer that settles it" value={text} onChange={(ev) => setText(ev.target.value)} style={{ flex: "1 1 240px" }} />
      <Button type="submit" disabled={!text.trim()}>Settle</Button>
    </form>
  );
}

function Section({ n, title, children, empty }: { n: number; title: string; children: ReactNode; empty: boolean }) {
  return (
    <section className="ds-card" style={{ padding: 16, marginBottom: 12 }}>
      <h2 style={{ margin: "0 0 8px" }}>{n}. {title}</h2>
      {empty ? <p className="ds-muted" style={{ margin: 0 }}>Nothing yet. North fills this as the thread goes on.</p> : children}
    </section>
  );
}

export default function SowPage() {
  const { iid = "" } = useParams<{ iid: string }>();
  const [sow, setSow] = useState<SowView | null>(null);
  const [state, setState] = useState<"loading" | "error" | "refused" | "empty" | "populated">("loading");
  const [message, setMessage] = useState<string | undefined>();
  const [problem, setProblem] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [sure, setSure] = useState(false);
  const [back, setBack] = useState(false);
  const [reason, setReason] = useState("");
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let live = true;
    getSow(iid)
      .then((d) => { if (live) { setSow(d); setState("populated"); } })
      .catch((e: unknown) => {
        if (!live) return;
        setMessage(e instanceof ApiError && e.status > 0 && e.status < 500 ? e.message : undefined);
        setState(e instanceof ApiError && e.status === 403 ? "refused" : e instanceof ApiError && e.status === 404 ? "empty" : "error");
      });
    return () => { live = false; };
  }, [iid, attempt]);

  const run = useCallback(async (work: () => Promise<SowView>) => {
    setBusy(true);
    setProblem(null);
    try { setSow(await work()); } catch (e) { setProblem(said(e)); throw e; } finally { setBusy(false); }
  }, []);

  if (state !== "populated" || !sow) {
    return <PageFrame title="Intent of work"><ScreenState state={state} message={message} onRetry={() => setAttempt((a) => a + 1)} /></PageFrame>;
  }
  const can = sow.may.edit && !busy;
  const save = (e: LineEdit) => run(() => editLine(iid, sow.version, e)).catch(() => undefined);
  const g = sow.goal;
  const steps = sow.process?.steps ?? [];
  const signed = sow.state === "signed";
  const fetchFile = (f: "md" | "docx") => download(iid, f).catch((e: unknown) => setProblem(said(e)));

  const aside = (
    <>
      <SideCard title="Signature">
        {sow.signature ? <Signature state="signed" by={sow.signature.name} at={day(sow.signature.at)} /> : <Signature state="waiting" by={sow.may.sign ? "your signature" : "the sponsor"} />}
        {!signed && sow.may.sign ? <Link className="ds-link" to={`/centre/intent/${encodeURIComponent(iid)}/sign`}>Open the signing page</Link> : null}
        {!signed && sow.sign_block ? <p role="status" className="ds-muted" style={{ margin: "8px 0 0" }}>{sow.sign_block}</p> : null}
        {sow.may.sign ? <Button variant="primary" disabled={busy} onClick={() => setSure(true)}>Sign</Button> : null}
        {sow.may.send_back ? <Button disabled={busy} onClick={() => setBack(true)}>Send back to North</Button> : null}
      </SideCard>
      <SideCard title="Download">
        <Button onClick={() => void fetchFile("md")}>Markdown</Button>
        {sow.docx ? <Button onClick={() => void fetchFile("docx")}>Word</Button> : null}
      </SideCard>
    </>
  );

  return (
    <PageFrame title={sow.title || "Intent of work"} crumbs={<Link className="ds-link" to={`/centre/intent/${encodeURIComponent(iid)}/thread`}>North's thread</Link>}
      subline={<><Pill tone={signed ? "signed" : "draft"}>{signed ? "Signed" : "Draft"}</Pill> Version {sow.version}</>} aside={aside}>
      {problem ? <p role="alert" className="ds-warn">{problem}</p> : null}
      {sow.written ? (
        <p role="status" className="ds-card" style={{ padding: 12 }}>
          {sow.written.catalogue.error ?? `Signed. The KPI definitions are in the company glossary; ${sow.written.catalogue.sources ?? 0} sources and ${sow.written.catalogue.tables ?? 0} tables were added to the catalogue. Span has been asked to draft the design.`}
        </p>
      ) : null}
      {can ? <Line label="Title" value={sow.title} edit={{ section: "title" }} can={can} save={save} /> : null}

      <Section n={1} title="Goal" empty={!g}>
        {g ? <>
          <Line label="Goal" value={g.line} edit={{ section: "goal", field: "line" }} can={can} save={save} />
          <Line label="Why" value={g.why} edit={{ section: "goal", field: "why" }} can={can} save={save} area />
          <Line label="Readers" value={list(g.readers)} edit={{ section: "goal", field: "readers" }} can={can} save={save} />
          <Line label="Decisions" value={list(g.decisions)} edit={{ section: "goal", field: "decisions" }} can={can} save={save} />
          <Line label="Needed by" value={g.needed_by} edit={{ section: "goal", field: "needed_by" }} can={can} save={save} />
        </> : null}
      </Section>

      <Section n={2} title="Process" empty={!steps.length}>
        <ol style={{ margin: 0, paddingLeft: 20 }}>
          {steps.map((s, i) => (
            <li key={s.n ?? i}>
              <Line label={s.name} value={s.does} edit={{ section: "process", index: i, field: "does" }} can={can} save={save} area />
              <p className="ds-muted" style={{ margin: 0 }}>{s.who || "Who not stated"} · {s.system || "System not stated"} · in: {list(s.inputs)} · out: {list(s.outputs)}</p>
            </li>
          ))}
        </ol>
        {(sow.process?.handovers ?? []).map((h, i) => <p key={i} className="ds-muted" style={{ margin: "4px 0" }}>Step {h.from_step} to step {h.to_step}: {h.what}</p>)}
      </Section>

      <Section n={3} title="KPIs" empty={!sow.kpis.length}>
        {sow.kpis.map((k, i) => (
          <div key={k.code || i} style={{ marginBottom: 10 }}>
            <strong>{k.code} {k.name}</strong>{" "}
            <Pill tone={k.status === "defined" ? "ok" : "open"}>{k.status === "defined" ? "Defined" : "Unclear"}</Pill>
            {k.pack_suggested ? <span className="ds-muted"> What others in the industry usually track</span> : null}
            <Line label="Definition" value={k.definition} edit={{ section: "kpis", index: i, field: "definition" }} can={can} save={save} area />
            <Line label="Formula" value={k.formula} edit={{ section: "kpis", index: i, field: "formula" }} can={can} save={save} />
            <Line label="Owner" value={k.owner} edit={{ section: "kpis", index: i, field: "owner" }} can={can} save={save} />
            <p className="ds-muted" style={{ margin: 0 }}>{k.unit || "-"} · {k.period || "-"} · sources: {list(k.source_ids)}</p>
          </div>
        ))}
      </Section>

      <Section n={4} title="Sources" empty={!sow.sources.length}>
        {sow.sources.map((s, i) => (
          <div key={s.id || i} style={{ marginBottom: 8 }}>
            <strong>{s.name}</strong> <span className="ds-muted">({s.kind === "document" ? "document" : s.kind === "system" ? "system" : "file"})</span>
            <Line label="Holds" value={s.holds} edit={{ section: "sources", index: i, field: "holds" }} can={can} save={save} />
            <Line label="Owner" value={s.owner} edit={{ section: "sources", index: i, field: "owner" }} can={can} save={save} />
            {s.fields?.length ? <p className="ds-muted" style={{ margin: 0 }}>Fields: {s.fields.map((f) => f.name).join(", ")}</p> : null}
          </div>
        ))}
      </Section>

      <Section n={5} title="Data catalogue" empty={!sow.catalogue.length}>
        {sow.catalogue.map((c, i) => (
          <div key={`${c.table}-${i}`} style={{ marginBottom: 8 }}>
            <strong>{c.table}</strong> <Pill tone="draft">{c.layer}</Pill>
            <Line label="Meaning" value={c.meaning} edit={{ section: "catalogue", index: i, field: "meaning" }} can={can} save={save} />
            <p className="ds-muted" style={{ margin: 0 }}>From {c.source_id || "several sources"} · feeds {list(c.feeds_kpis)} · {c.fields?.length ?? 0} fields</p>
          </div>
        ))}
      </Section>

      <Section n={6} title="Governance" empty={!sow.governance.length}>
        {sow.governance.map((r, i) => (
          <div key={i}>
            <Line label={r.kind === "access" ? "Access" : r.kind === "retention" ? "Retention" : "Approval"} value={r.rule} edit={{ section: "governance", index: i, field: "rule" }} can={can} save={save} />
            <p className="ds-muted" style={{ margin: 0 }}>Applies to {list(r.applies_to)} · stated by {r.stated_by || "not named"}</p>
          </div>
        ))}
      </Section>

      <Section n={7} title="Unclear" empty={!sow.unclear.length}>
        {sow.unclear.map((u, i) => (
          <div key={u.id || i} style={{ marginBottom: 8 }}>
            <p style={{ margin: 0 }}><Pill tone={u.settled ? "ok" : "open"}>{u.settled ? "Settled" : "Open"}</Pill> {u.question}</p>
            {u.settled ? <p className="ds-muted" style={{ margin: 0 }}>Answer: {u.answer}</p>
              : <p className="ds-muted" style={{ margin: 0 }}>About {u.about || "the work"} · {u.who_can_settle || "who can settle is not named"}</p>}
            {!u.settled && can ? <Settle question={u.question} save={(answer) => save({ section: "unclear", index: i, field: "answer", value: answer })} /> : null}
          </div>
        ))}
      </Section>

      <Section n={8} title="Signature" empty={false}>
        <p style={{ margin: 0 }}>{sow.signature ? `Signed by ${sow.signature.name} on ${day(sow.signature.at)}. The intent of work is now read-only.` : "Not signed yet. One signature, by the sponsor."}</p>
        {(sow.signatures ?? []).filter((x) => x.version !== sow.version).map((x) => (
          <p key={x.version} className="ds-muted" style={{ margin: "4px 0 0" }}>Version {x.version} was signed by {x.name} on {day(x.at)}.</p>
        ))}
      </Section>

      {sure ? (
        <div role="dialog" aria-modal="true" aria-label="Sign the intent of work" className="ds-card" style={{ padding: 16, position: "sticky", bottom: 16 }}>
          <p style={{ marginTop: 0 }}>I sign version {sow.version} of “{sow.title}”. Its KPI definitions go to the company glossary, its tables to the catalogue, and Span starts the design from it. It cannot be changed afterwards.</p>
          <Button variant="primary" disabled={busy} onClick={() => { setSure(false); void run(() => signSow(iid, sow.version)).catch(() => undefined); }}>Yes, I sign</Button>{" "}
          <Button onClick={() => setSure(false)}>Not yet</Button>
        </div>
      ) : null}
      {back ? (
        <form className="ds-card" style={{ padding: 16 }} onSubmit={(ev) => { ev.preventDefault(); void run(() => sendBack(iid, reason)).then(() => { setBack(false); setReason(""); }).catch(() => undefined); }}>
          <label htmlFor="i4-back">What should North change?</label>
          <textarea id="i4-back" className="ds-input" value={reason} onChange={(ev) => setReason(ev.target.value)} style={{ width: "100%" }} />
          <Button variant="primary" type="submit" disabled={busy || !reason.trim()}>Send back</Button>{" "}
          <Button onClick={() => setBack(false)}>Cancel</Button>
        </form>
      ) : null}
    </PageFrame>
  );
}
