import { getNote } from "../api";
import V3Frame from "../Frame";
import { DeskLink, Failed, Page, Waiting, sourceOf, useRead } from "./common";

const day = (at: string) => {
  const d = new Date(at);
  return Number.isNaN(d.getTime()) ? at : d.toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" });
};

export default function NotePage() {
  const [got, again] = useRead(getNote);
  return (
    <V3Frame>
      <Page>
        <div className="v3b-head"><h1>The morning note</h1><DeskLink /></div>
        {got.state === "loading" ? <Waiting what="Reading today's note…" />
          : got.state === "error" ? <Failed message={got.message} again={again} />
          : (
            <>
              <section className="v3-note" aria-labelledby="h-today">
                <h2 id="h-today">Today&apos;s note</h2>
                {got.data.text ? (
                  <>
                    <p>{got.data.text}</p>
                    {got.data.figures.length ? (
                      <ol className="v3b-list" aria-label="Figures in the note">
                        {got.data.figures.map((f, i) => {
                          const src = sourceOf(f);
                          return (
                            <li key={f.label} className="v3b-item">
                              <span className="n" aria-hidden="true">{i + 1}</span>
                              <div>
                                <span>{f.label}: <b className="num" title={src ? `Where this is from: ${src}` : undefined}>{f.value}</b></span>
                                {f.change ? <small className="v3-mute" style={{ display: "block" }}>{f.change}</small> : null}
                              </div>
                            </li>
                          );
                        })}
                      </ol>
                    ) : null}
                    <p className="v3-mute">Every figure traces to a run and a file; hover a number to see which.</p>
                  </>
                ) : <p>There is no note yet. The first one is written when a thread goes live.</p>}
              </section>
              <section aria-labelledby="h-past">
                <h2 id="h-past">Past notes</h2>
                {got.data.history.length ? (
                  <ul className="v3b-list">{got.data.history.map((h) => <li key={h.at} className="v3-link"><b><span>{day(h.at)}</span></b><small>{h.headline}</small></li>)}</ul>
                ) : <p className="v3-mute">Past notes will be listed here.</p>}
              </section>
            </>
          )}
      </Page>
    </V3Frame>
  );
}
