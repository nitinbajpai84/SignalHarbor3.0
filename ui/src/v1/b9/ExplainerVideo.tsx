import { useEffect, useRef, useState } from "react";

import StepIcon from "./StepIcons";
import type { StepId } from "./steps";
import "./b9.css";

// V5 design A1: the explainer on the Build landing. Plays /static/explainer.mp4 when that file is served (the launch film,
// docs/video/out/signal-harbor-launch-60s.mp4); otherwise it shows the poster (title, play button, the four step icons) and the chapters as plain text.
export const EXPLAINER_SRC = "/static/explainer.mp4";
export const CHAPTERS: { at: number; time: string; title: string; line: string; icon: StepId | "deliver" }[] = [
  { at: 0, time: "0:00", title: "Say what you need", line: "You talk to North. It writes the brief with you.", icon: "intent" },
  { at: 20, time: "0:20", title: "The data team builds", line: "Span maps the brief to your data. A data engineer checks it.", icon: "architecture" },
  { at: 45, time: "0:45", title: "Check the numbers", line: "A trial run on a copy, compared with last month's report.", icon: "pipelines" },
  { at: 65, time: "1:05", title: "Design what people see", line: "Lumen lays out the views. Someone else approves.", icon: "dashboards" },
  { at: 80, time: "1:20", title: "Deliver", line: "Reports in Consume, the Morning Note, email or Teams.", icon: "deliver" },
];
const POSTER_STEPS: StepId[] = ["intent", "architecture", "pipelines", "dashboards"];

/** True when the film is really served: the server may answer an unknown path with the app page, so the type must be a video. */
function useFilmServed(): boolean {
  const [served, setServed] = useState(false);
  useEffect(() => {
    let live = true;
    fetch(EXPLAINER_SRC, { method: "HEAD" })
      .then((r) => { if (live) setServed(r.ok && (r.headers.get("content-type") ?? "").startsWith("video")); })
      .catch(() => undefined); // no film: the poster stands
    return () => { live = false; };
  }, []);
  return served;
}

export default function ExplainerVideo() {
  const served = useFilmServed();
  const ref = useRef<HTMLVideoElement>(null);
  const jump = (at: number) => { const v = ref.current; if (!v) return; v.currentTime = at; void v.play?.(); };
  return (
    <section className="b9-video" aria-label="How a project works">
      <div className="b9-poster">
        {served ? <video ref={ref} src={EXPLAINER_SRC} controls preload="metadata" aria-label="How a project works, a short film" /> : null}
        {served ? null : (
          <>
            <div className="b9-poster__top"><span className="b9-eyebrow">SIGNAL HARBOR · BUILD</span><span className="b9-dur">1:30</span></div>
            <div className="b9-poster__mid">
              <h2 className="ds-serif">From a need in your words to a report people receive</h2>
              <span className="b9-play" role="img" aria-label="The film is not available on this machine yet"><svg viewBox="0 0 24 24" width="30" height="30" aria-hidden="true"><path d="M8 5l11 7-11 7z" fill="currentColor" /></svg></span>
            </div>
            <ol className="b9-poster__steps" aria-hidden="true">
              {POSTER_STEPS.map((s, i) => <li key={s}><span className="b9-ico"><StepIcon step={s} size={20} /></span>{i < POSTER_STEPS.length - 1 ? <span className="b9-arr">→</span> : null}</li>)}
            </ol>
            <p className="b9-poster__bar"><strong>How a project works in 90 seconds</strong><span>Captions on · no sound needed</span></p>
          </>
        )}
      </div>
      <div className="b9-chapters-card">
        <div className="b9-chapters-head">
          <h2 style={{ margin: 0, fontSize: 18 }}>Chapters</h2>
          <p className="ds-muted" style={{ margin: 0, fontSize: 13 }}>{served ? "Jump to any part" : "The film is not available on this machine yet."}</p>
        </div>
        <ol className="b9-chapters">
          {CHAPTERS.map((c) => {
            const body = <><span className="b9-time">{c.time}</span><span className="b9-ico b9-ico--bare"><StepIcon step={c.icon} size={18} /></span><span><strong>{c.title}</strong><small>{c.line}</small></span></>;
            return <li key={c.time}>{served ? <button type="button" onClick={() => jump(c.at)}>{body}</button> : <div className="b9-chapter-row">{body}</div>}</li>;
          })}
        </ol>
      </div>
    </section>
  );
}
