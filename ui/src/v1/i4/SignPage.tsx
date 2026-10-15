import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { ApiError } from "../../api/client";
import ScreenState from "../../components/ScreenState";
import { Button, PageFrame, Pill, SideCard } from "../../design";
import { projectOf, type Project } from "../p1/api";
import { getSow, sendBack, signSow, type SowView } from "./api";

// V6 design B3: /centre/intent/:iid/sign. The sponsor's own page: what is waiting for the signature, who finished it and when, the intent
// in numbered sections, one signature with a note to the person who raised it, or send it back with a note. Reads and writes the I4 record
// (getSow, signSow, sendBack); the page decides nothing the record does not say.
const said = (e: unknown) => (e instanceof ApiError && e.message ? e.message : "That did not work. Please try again.");
const list = (xs: string[] | undefined) => (xs && xs.length ? xs.join(", ") : "");
const when = (at: string) => {
  const d = new Date(at);
  return `${d.toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "short" })} at ${d.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" })}`;
};
const day = (at: string) => new Date(at).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" });

/** The intent as numbered sections: only a section the record has anything in. */
export function sectionsOf(sow: SowView): { title: string; lines: string[] }[] {
  const g = sow.goal;
  const out = [
    { title: "Purpose", lines: g ? [g.line, g.why].filter(Boolean) : [] },
    { title: "Who reads it", lines: g ? [[list(g.readers), g.needed_by && `needed ${g.needed_by}`].filter(Boolean).join(", ")].filter(Boolean) : [] },
    { title: "Questions it answers", lines: g && g.decisions.length ? [list(g.decisions)] : [] },
    { title: "Measures and figures", lines: sow.kpis.map((k) => `${k.name}${k.definition ? `: ${k.definition}` : ""}${k.formula ? ` (${k.formula})` : ""}`) },
    { title: "Sources", lines: sow.sources.map((s) => `${s.name}${s.holds ? `: ${s.holds}` : ""}`) },
    { title: "How it is done today", lines: (sow.process?.steps ?? []).map((s) => `${s.name}${s.who ? ` (${s.who})` : ""}: ${s.does}`) },
    { title: "Rules and checks", lines: sow.governance.map((r) => r.rule) },
    { title: "Still unclear", lines: sow.unclear.filter((u) => !u.settled).map((u) => u.question) },
  ];
  return out.filter((s) => s.lines.length > 0);
}

export default function SignPage() {
  const { iid = "" } = useParams<{ iid: string }>();
  const [sow, setSow] = useState<SowView | null>(null);
  const [prj, setPrj] = useState<Project | null>(null);
  const [state, setState] = useState<"loading" | "error" | "refused" | "empty" | "populated">("loading");
  const [message, setMessage] = useState<string | undefined>();
  const [problem, setProblem] = useState<string | null>(null);
  const [read, setRead] = useState(false);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<"signed" | "sent_back" | null>(null);
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
    projectOf(iid).then((p) => { if (live) setPrj(p); }).catch(() => undefined); // the names beside the signature are a courtesy; the page stands without them
    return () => { live = false; };
  }, [iid, attempt]);

  if (state !== "populated" || !sow) return <PageFrame title="Sign the intent"><ScreenState state={state} message={message} onRetry={() => setAttempt((a) => a + 1)} /></PageFrame>;

  const raiser = sow.before?.by ?? prj?.people.raiser ?? "the person who raised it";
  const first = raiser.split(" ")[0] || raiser;
  const head = prj?.people.head_of_data;
  const sections = sectionsOf(sow);
  const signed = sow.state === "signed";
  const act = async (work: () => Promise<SowView>, how: "signed" | "sent_back") => {
    setBusy(true); setProblem(null);
    try { setSow(await work()); setDone(how); } catch (e) { setProblem(said(e)); } finally { setBusy(false); }
  };

  const aside = (
    <>
      <SideCard title="Your signature">
        {signed || done ? (
          <p role="status" style={{ margin: 0 }}>
            {done === "sent_back" ? `Sent back to ${first} with your note.` : `Signed by ${sow.signature?.name ?? "you"}${sow.signature ? ` on ${day(sow.signature.at)}` : ""}. ${first} has been told and picks who builds it.`}
          </p>
        ) : (
          <>
            <p style={{ marginTop: 0 }}>By signing you agree this is what the office needs. Nothing is built until you sign. Once signed, the build opens and any change to the intent comes back to you.</p>
            <label style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <input type="checkbox" checked={read} onChange={(e) => setRead(e.target.checked)} /> I have read all {sections.length} sections
            </label>
            <label style={{ display: "flex", flexDirection: "column", gap: 4, margin: "12px 0" }}>Note to {first} (optional)
              <textarea className="ds-input" rows={3} value={note} onChange={(e) => setNote(e.target.value)} maxLength={500} />
            </label>
            {sow.sign_block ? <p role="status" className="ds-muted">{sow.sign_block}</p> : null}
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <Button variant="primary" disabled={busy || !read || !sow.may.sign} onClick={() => void act(() => signSow(iid, sow.version, note), "signed")}>Sign intent</Button>
              <Button disabled={busy || !sow.may.send_back || !note.trim()} title={note.trim() ? undefined : "Write what should change in the note first"}
                onClick={() => void act(() => sendBack(iid, note.trim()), "sent_back")}>Send back with a note</Button>
            </div>
          </>
        )}
        {problem ? <p role="alert" className="ds-warn">{problem}</p> : null}
      </SideCard>
      <SideCard title="What happens when you sign">
        <ol style={{ margin: 0, paddingLeft: 18, display: "grid", gap: 6 }}>
          <li>{first} is told and picks who builds it.</li>
          <li>Span drafts the design; {head ?? "the head of data"} approves it.</li>
          <li>The first run is checked against the figures in this intent before it goes live.</li>
        </ol>
      </SideCard>
      <SideCard title="Who can read it">
        <ul style={{ margin: 0, paddingLeft: 18 }}>
          {prj?.people.raiser ? <li>{prj.people.raiser} · business owner</li> : null}
          {prj?.people.sponsor ? <li>{prj.people.sponsor} · sponsor</li> : null}
          {head ? <li>{head} · head of data</li> : null}
          {!prj?.people.raiser && !prj?.people.sponsor && !head ? <li className="ds-muted">The people named on the project.</li> : null}
        </ul>
      </SideCard>
    </>
  );

  return (
    <PageFrame title={`Sign the intent: ${sow.title || "intent of work"}`} crumbs={<Link className="ds-link" to="/centre/action">Back to today</Link>}
      subline={<><span className="ds-eyebrow" data-tone="amber">{signed ? "SIGNED" : "WAITING FOR YOUR SIGNATURE"}</span></>} aside={aside}>
      <p style={{ margin: 0 }}>
        {sow.before ? <>Before this: {raiser} finished this with North on {when(sow.before.at)}, after {sow.before.minutes} {sow.before.minutes === 1 ? "minute" : "minutes"}.</> : null}
      </p>
      {signed ? null : <p style={{ margin: 0 }}>Next: sign it, or send it back to {first} with a note.</p>}
      <article className="ds-card" style={{ padding: 20 }} aria-label="The intent of work">
        <p className="ds-eyebrow" style={{ margin: 0 }}>INTENT OF WORK · VERSION {sow.version} <Pill tone={signed ? "signed" : "draft"}>{signed ? "Signed" : "Draft"}</Pill></p>
        <h2 className="ds-serif" style={{ margin: "6px 0 16px", fontSize: 24 }}>{sow.title}</h2>
        {sections.length === 0 ? <p className="ds-muted">Nothing is written in this intent yet.</p> : (
          <ol style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: 14 }}>
            {sections.map((s, i) => (
              <li key={s.title} style={{ display: "grid", gridTemplateColumns: "32px 1fr", gap: 8 }}>
                <span className="ds-eyebrow">{String(i + 1).padStart(2, "0")}</span>
                <span><strong>{s.title}</strong>{s.lines.map((l, j) => <span key={j} style={{ display: "block", color: "var(--ds-ink-soft)" }}>{l}</span>)}</span>
              </li>
            ))}
          </ol>
        )}
      </article>
      <p className="ds-muted" style={{ margin: 0 }}>Want to edit a line first? <Link className="ds-link" to={`/centre/intent/${encodeURIComponent(iid)}/sow`}>Open the full intent of work</Link>.</p>
    </PageFrame>
  );
}
