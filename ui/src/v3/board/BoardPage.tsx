import { useState } from "react";
import { Link } from "react-router-dom";

import { ask, getBoard, type AskAnswer, type Tile } from "../api";
import type { Tile as CxTile } from "../../v1/cxui/api";
import TileCard from "../../v1/cxui/TileCard";
import V3Frame from "../Frame";
import { AnswerCard, AskBox, Failed, FigureCard, Page, Waiting, useRead } from "./common";

const str = (v: unknown) => (typeof v === "string" ? v : "");
/** A 2.0 tile as the board sends it, in the shape the chart card reads. */
const asTile = (t: Tile): CxTile => ({
  id: str(t.id), title: str(t.title), kpi: str(t.kpi), sql: "", spec: (t.spec ?? {}) as Record<string, unknown>, note: str(t.note), state: "accepted",
});

export default function BoardPage() {
  const [got, again] = useRead(getBoard);
  const [asked, setAsked] = useState<{ q: string; a: AskAnswer | null; error?: string } | null>(null);
  const run = (q: string) => {
    setAsked({ q, a: null });
    ask(q).then((a) => setAsked({ q, a }), (e: unknown) => setAsked({ q, a: null, error: e instanceof Error && e.message ? e.message : "I could not answer that just now." }));
  };
  return (
    <V3Frame>
      <Page>
        {got.state === "loading" ? <Waiting what="Opening the board…" />
          : got.state === "error" ? <Failed message={got.message} again={again} />
          : got.data.tiles.length === 0 && got.data.figures.length === 0 ? (
            <div className="v3-card" aria-label="No board yet">
              <h1>No board yet</h1>
              <p>A board appears here once a thread has gone live and its first dashboard is published.</p>
              <div className="v3-row"><Link to="/v3/desk">Open the Desk</Link></div>
            </div>
          ) : (
            <>
              <section className="v3b-head" aria-labelledby="h-board">
                <h1 id="h-board">{got.data.title || "The board"}</h1>
                <span className="v3-mute">Signed numbers{got.data.as_at ? ` · as at ${got.data.as_at.slice(0, 10)}` : ""}</span>
              </section>
              {got.data.figures.length ? <section className="v3b-figs" aria-label="Headline numbers">{got.data.figures.map((f) => <FigureCard key={f.label} f={f} />)}</section> : null}
              <div className="v3b-split">
                <div className="v3b-tiles">
                  {got.data.tiles.map((t) => <TileCard key={str(t.id)} pid={str(t.project_id)} did={str(t.dashboard_id)} tile={asTile(t)} inGrid />)}
                </div>
                <aside className="v3b-side" aria-labelledby="h-ask">
                  <h2 id="h-ask">Ask about this board</h2>
                  <span className="v3-mute">Harbor answers from the signed numbers and cites its source</span>
                  <AskBox onAsk={run} busy={!!asked && !asked.a && !asked.error} label="Ask about this board" />
                  {asked ? <p className="v3-mute">{asked.q}</p> : null}
                  {asked?.a ? <AnswerCard a={asked.a} /> : asked?.error ? <p className="v3-err" role="alert">{asked.error}</p> : asked ? <Waiting what="Working it out…" /> : null}
                </aside>
              </div>
            </>
          )}
      </Page>
    </V3Frame>
  );
}
