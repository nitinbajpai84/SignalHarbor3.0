import { useEffect, useState, type ReactNode } from "react";
import { Link, NavLink } from "react-router-dom";

import type { AskAnswer, Figure } from "../api";
import "./board.css";

/** The place a number came from, when the server could trace it (a `source` key on the figure). */
export const sourceOf = (f: Figure): string | undefined => {
  const s = (f as Figure & { source?: unknown }).source;
  return typeof s === "string" && s ? s : undefined;
};

export type Loaded<T> = { state: "loading" } | { state: "error"; message: string } | { state: "ready"; data: T };

/** Run one read when the page opens; `again()` reads it once more. */
export function useRead<T>(read: () => Promise<T>): [Loaded<T>, () => void] {
  const [n, setN] = useState(0);
  const [got, setGot] = useState<Loaded<T>>({ state: "loading" });
  useEffect(() => {
    let live = true;
    setGot({ state: "loading" });
    read().then(
      (data) => { if (live) setGot({ state: "ready", data }); },
      (e: unknown) => { if (live) setGot({ state: "error", message: e instanceof Error && e.message ? e.message : "Something went wrong. Please try again." }); },
    );
    return () => { live = false; };
  }, [n]); // eslint-disable-line react-hooks/exhaustive-deps -- `read` is new on every render; `n` says when to read again
  return [got, () => setN((x) => x + 1)];
}

export function Failed({ message, again }: { message: string; again: () => void }) {
  return <div className="v3-card" role="alert"><p className="v3-err">{message}</p><div className="v3-row"><button type="button" onClick={again}>Try again</button></div></div>;
}

export const Waiting = ({ what }: { what: string }) => <p className="v3-mute" role="status">{what}</p>;

/** One figure: the value shows where it came from on hover (and to a screen reader) when the trace exists. */
export function FigureCard({ f }: { f: Figure }) {
  const src = sourceOf(f);
  return (
    <article className="v3b-fig" aria-label={f.label}>
      <small>{f.label}</small>
      <span className="num" title={src ? `Where this is from: ${src}` : undefined}>{f.value}</span>
      {f.change ? <small className={/^[-−]/.test(f.change) ? "v3b-down" : /^\+/.test(f.change) ? "v3b-up" : undefined}>{f.change}</small> : null}
    </article>
  );
}

/** Lumen's answer with how it was worked out and what it used. */
export function AnswerCard({ a }: { a: AskAnswer }) {
  return (
    <article className="v3-card v3b-answer" aria-label="Harbor's answer">
      {a.figure ? <FigureCard f={a.figure} /> : null}
      <p>{a.answer}</p>
      {a.understood ? <p className="v3-mute">How I understood you: {a.understood}</p> : null}
      {a.trace.length ? (
        <div>
          <span className="v3-kicker">Where this is from</span>
          <ol className="v3b-chain">{a.trace.map((s, i) => <li key={i} data-kind={s.kind}>{s.label}</li>)}</ol>
        </div>
      ) : null}
      {a.used.length ? <p className="v3b-used">{a.used.join("; ")}</p> : null}
    </article>
  );
}

/** The ask box: shared by the Board and the Ask page. */
export function AskBox({ onAsk, busy, label = "Ask about any number" }: { onAsk: (q: string) => void; busy: boolean; label?: string }) {
  const [q, setQ] = useState("");
  return (
    <form className="v3b-ask" onSubmit={(e) => { e.preventDefault(); if (q.trim()) onAsk(q.trim()); }}>
      <label className="v3b-sr" htmlFor="v3b-q">{label}</label>
      <input id="v3b-q" type="text" value={q} placeholder={label} onChange={(e) => setQ(e.target.value)} />
      <button type="submit" className="go" disabled={busy || !q.trim()}>Ask</button>
    </form>
  );
}

/** Phone only (under 720px wide): the three reading places, as a sticky row at the top (Frame owns the bottom bar). */
export function PhoneBar() {
  return (
    <nav className="v3b-phone" aria-label="Main">
      <NavLink to="/v3/note">Note</NavLink>
      <NavLink to="/v3/board">Board</NavLink>
      <NavLink to="/v3/ask">Ask</NavLink>
    </nav>
  );
}

export function Page({ children }: { children: ReactNode }) {
  return <main className="v3b-main"><PhoneBar />{children}</main>;
}

export const DeskLink = () => <Link to="/v3/desk">Back to the Desk</Link>;
