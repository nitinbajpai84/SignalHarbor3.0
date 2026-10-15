import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { ask, getLanguage, type AskAnswer } from "../api";
import V3Frame from "../Frame";
import { AnswerCard, AskBox, Page, Waiting } from "./common";

type Turn = { q: string; a: AskAnswer | null; error?: string };

export default function AnswerPage() {
  const [params] = useSearchParams();
  const [turn, setTurn] = useState<Turn | null>(null);
  const [golden, setGolden] = useState<string[]>([]);
  const first = useRef(true);
  const run = (q: string) => {
    setTurn({ q, a: null });
    ask(q).then((a) => setTurn({ q, a }), (e: unknown) => setTurn({ q, a: null, error: e instanceof Error && e.message ? e.message : "I could not answer that just now. Please try again." }));
  };
  useEffect(() => {
    getLanguage().then((l) => setGolden(l.golden.map((g) => g.q)), () => setGolden([]));
    const q = params.get("q");
    if (first.current && q) run(q);
    first.current = false;
  }, []); // eslint-disable-line react-hooks/exhaustive-deps -- once, on opening
  const busy = !!turn && !turn.a && !turn.error;
  return (
    <V3Frame>
      <Page>
        <div className="v3b-split">
          <section className="v3-col" style={{ flex: "3 1 520px" }} aria-labelledby="h-ask">
            <span className="v3-kicker">Ask anything</span>
            <h1 id="h-ask">{turn ? turn.q : "What would you like to know?"}</h1>
            <AskBox onAsk={run} busy={busy} label="Ask about any number" />
            {!turn ? <p className="v3-mute">Ask in your own words. Harbor answers from the signed numbers and shows where each one is from.</p>
              : busy ? <Waiting what="Working it out…" />
              : turn.error ? <div className="v3-card" role="alert"><p className="v3-err">{turn.error}</p><div className="v3-row"><button type="button" onClick={() => run(turn.q)}>Try again</button></div></div>
              : turn.a ? <AnswerCard a={turn.a} /> : null}
          </section>
          <aside className="v3b-side" aria-labelledby="h-golden">
            <h2 id="h-golden">Questions people here ask often</h2>
            {golden.length ? <div className="v3b-golden">{golden.map((q) => <button key={q} type="button" onClick={() => run(q)} disabled={busy}>{q}</button>)}</div>
              : <p className="v3-mute">No saved questions yet. They appear here once the office teaches Harbor some.</p>}
          </aside>
        </div>
      </Page>
    </V3Frame>
  );
}
