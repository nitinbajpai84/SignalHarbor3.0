import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import V3Frame from "../Frame";
import { decide, getDesk, getThread, say, type Card, type Event } from "../api";
import { listSkills, when, type SkillRow } from "./actionApi";
import "./action.css";

/** A desk card may carry the case it belongs to; the 3.0 desk shape does not name it, so it is optional here. */
type NeedCard = Card & { case?: string };
type Kind = "decision" | "exception" | "question" | "skill";
interface Item { key: string; kind: Kind; title: string; text: string; card?: NeedCard; skill?: SkillRow }
interface Done { by: string; at: string; text: string; thread: string }
interface Loaded { items: Item[]; done: Done[]; skillsFailed: boolean }
interface ThreadEvents { id: string; title: string; events: Event[] }

const STEP: Record<string, 1 | 2 | 3> = { confirm: 1, carry_on: 2, go_live: 3 };
const LABEL: Record<Kind, string> = { decision: "Decision", exception: "Exception", question: "Question", skill: "New skill to review" };
const PLURAL: Record<Kind, string> = { decision: "Decisions", exception: "Exceptions", question: "Questions", skill: "New skills" };
const KINDS: Kind[] = ["decision", "exception", "question", "skill"];
const WEEK = 7 * 24 * 3600 * 1000;

async function load(): Promise<Loaded> {
  const desk = await getDesk();
  const [sk, ...threads] = await Promise.allSettled([listSkills(), ...desk.threads.map((t) => getThread(t.id))]);
  const skills = sk.status === "fulfilled" ? (sk.value as { skills: SkillRow[] }).skills.filter((s) => s.status === "waiting") : [];
  const items: Item[] = [
    ...desk.needs.map((c, i): Item => ({ key: `c-${c.thread}-${i}`, kind: c.kind, title: c.title, text: c.text, card: c })),
    ...skills.map((s): Item => ({ key: `s-${s.id}`, kind: "skill", title: s.name, text: s.goal, skill: s })),
  ];
  const since = Date.now() - WEEK;
  const done: Done[] = [];
  for (const r of threads) {
    if (r.status !== "fulfilled") continue;
    const t = r.value as ThreadEvents;
    for (const e of t.events) {
      if (e.kind === "decision_done" && new Date(e.at).getTime() >= since) done.push({ by: e.by ?? "", at: e.at, text: e.text ?? t.title, thread: t.id });
    }
  }
  done.sort((a, b) => b.at.localeCompare(a.at));
  return { items, done, skillsFailed: sk.status === "rejected" };
}

const Head = ({ children }: { children?: React.ReactNode }) => (
  <section aria-labelledby="h-action" className="act-head">
    <div>
      <span className="act-eyebrow">Action centre</span>
      <h1 id="h-action">Needs a person</h1>
    </div>
    {children}
  </section>
);

export default function ActionPage() {
  const [data, setData] = useState<Loaded | null>(null);
  const [failed, setFailed] = useState(false);
  const [filter, setFilter] = useState<Kind | "all">("all");
  const [sel, setSel] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState("");

  const reload = useCallback(() => {
    setFailed(false);
    load().then(setData, () => setFailed(true));
  }, []);
  useEffect(reload, [reload]);

  async function act(c: Card, answer: string) {
    setBusy(true);
    setProblem("");
    try {
      const n = STEP[answer];
      if (n) await decide(c.thread, n, answer);
      else await say(c.thread, answer);
      setSel(null);
      reload();
    } catch {
      setProblem("That did not go through. Try again.");
    } finally {
      setBusy(false);
    }
  }

  if (failed) return <V3Frame><Head /><p className="v3-err act-empty" role="alert">The Action centre did not load. <button type="button" onClick={reload}>Try again</button></p></V3Frame>;
  if (!data) return <V3Frame><Head /><p className="v3-mute act-empty" role="status">Loading what needs a person...</p></V3Frame>;

  const count = (k: Kind) => data.items.filter((i) => i.kind === k).length;
  const shown = data.items.filter((i) => filter === "all" || i.kind === filter);
  const open = data.items.find((i) => i.key === sel) ?? null;

  return (
    <V3Frame>
      <Head>
        <div role="group" aria-label="Filter by kind" className="act-pills">
          <button type="button" className="act-pill" aria-pressed={filter === "all"} onClick={() => setFilter("all")}>All <span className="num">{data.items.length}</span></button>
          {KINDS.map((k) => (
            <button key={k} type="button" className="act-pill" aria-pressed={filter === k} onClick={() => setFilter(k)}>{PLURAL[k]} <span className="num">{count(k)}</span></button>
          ))}
        </div>
        {data.skillsFailed && <p className="v3-err" role="alert">Skills waiting for review did not load.</p>}
      </Head>

      <div className="act-main" data-open={open ? "true" : "false"}>
        <section aria-label="Queue" className="act-queue">
          {!shown.length && <p className="v3-mute">{data.items.length ? "Nothing of this kind needs a person." : "Nothing needs a person right now."}</p>}
          {shown.map((i) => (
            // The whole card opens it (a tap on a phone); the Open button toggles it and is the keyboard way in.
            <article key={i.key} className={`act-item ${i.kind}`} data-on={i.key === sel} onClick={() => { if (i.key !== sel) { setSel(i.key); setProblem(""); window.scrollTo?.(0, 0); } }}>
              <div className="v3-head">
                <span className="v3-kicker">{LABEL[i.kind]}</span>
                <button type="button" className="act-open" aria-pressed={i.key === sel} aria-label={`Open ${i.title}`} onClick={(e) => { e.stopPropagation(); setSel(i.key === sel ? null : i.key); setProblem(""); }}>Open</button>
              </div>
              <b className="act-title">{i.title}</b>
              <p>{i.text}</p>
            </article>
          ))}
        </section>

        <section aria-label="Selected" className="act-detail">
          {!open ? <p className="v3-mute">Pick one from the list to see what Harbor needs from you.</p> : (
            <>
              <button type="button" className="act-back" onClick={() => setSel(null)}>&larr; Back to the list</button>
              <div>
                <span className="v3-kicker">{LABEL[open.kind]}</span>
                <h2>{open.title}</h2>
              </div>
              <div className="act-dark"><span className="act-h3"><span className="v3-av harbor" aria-hidden="true">H</span>What Harbor is asking</span><p>{open.text}</p></div>
              {problem && <p className="v3-err" role="alert">{problem}</p>}
              <div className="v3-row">
                {open.skill && <Link className="act-go" to={`/v3/skill/${encodeURIComponent(open.skill.id)}`}>Review</Link>}
                {open.card?.actions.map((a, j) => (
                  <button key={a.answer + j} type="button" className={j === 0 ? "go" : ""} disabled={busy} onClick={() => void act(open.card as Card, a.answer)}>{a.label}</button>
                ))}
                {open.card?.case && <Link to={`/v3/case/${encodeURIComponent(open.card.case)}`}>Review the case</Link>}
                {open.card && <Link to={`/v3/thread/${encodeURIComponent(open.card.thread)}`}>Open the thread</Link>}
              </div>
            </>
          )}
        </section>
      </div>

      <section aria-labelledby="h-done" className="act-done">
        <div>
          <h2 id="h-done">Done this week</h2>
          {!data.done.length ? <p className="v3-mute">Nothing answered yet this week.</p> : (
            <ul>
              {data.done.map((d, i) => (
                <li key={`${d.thread}-${i}`}>
                  <small><b>{d.by || "Someone"}</b> · {when(d.at)}</small>
                  <span>{d.text}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>
    </V3Frame>
  );
}
