import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { time } from "../../design";
import { getThread, type Comment } from "../n2/api";
import { getNote, type Note } from "./api";
import { Loading, WhereLink, compact, pct, plain } from "./format";
import "./slack.css";

// E7: the Morning Note as Lumen posts it in Slack, with the replies people left on today's note shown as the thread. The post is built from the same note as the
// Consume page; the replies are the comments on that note. A reply is shown only when someone wrote it: nothing is made up for the picture.
function chips(n: Note): string[] {
  return n.tiles.filter((t) => t.available && t.value !== null).slice(0, 4).map((t) => `${t.kind === "percent" ? pct(t.value) : t.kind === "count" ? t.value : compact(t.value, t.currency)} ${t.label.toLowerCase()}`);
}

export default function SlackThread({ ccy }: { ccy: string }) {
  const [n, setN] = useState<Note | null>(null);
  const [replies, setReplies] = useState<Comment[]>([]);
  const [error, setError] = useState("");
  useEffect(() => {
    let live = true;
    setN(null); setError("");
    getNote(ccy).then((r) => {
      if (!live) return;
      setN(r);
      getThread(r.comment_target).then((t) => { if (live) setReplies(t.comments.filter((c) => !c.deleted)); }, () => { if (live) setReplies([]); });
    }, (e) => { if (live) setError(plain(e)); });
    return () => { live = false; };
  }, [ccy]);
  if (error) return <p role="alert">{error}</p>;
  if (!n) return <Loading what="the Slack preview" />;
  return (
    <>
      <p className="ds-muted" style={{ letterSpacing: 1, fontSize: "0.8rem", margin: 0 }}>DELIVERY PREVIEW · IN SLACK</p>
      <h3 style={{ margin: "4px 0" }}>The Morning Note, and a question answered in the thread</h3>
      <p>This is how Lumen posts the note in your Slack channel. Replies in the thread are the comments left on the note.</p>
      <div className="slack" role="region" aria-label="Slack preview">
        <div className="slack-msg"><span className="slack-av">L</span>
          <div><strong>Lumen</strong> <span className="slack-app">APP</span> <span className="ds-muted">{n.dateline}</span>
            <p>{n.headline}</p>
            {chips(n).length ? <div className="slack-chips">{chips(n).map((c) => <span key={c} className="slack-chip">{c}</span>)}</div> : null}
            <p className="ds-muted"><WhereLink label="Where is this from?" where={n.tiles[0]?.where} id={n.tiles[0]?.trail_id} /> <Link className="ds-link" to="/centre/consume">Open Signal Harbor</Link></p>
            <p className="ds-muted">{replies.length === 0 ? "No replies yet" : `${replies.length} repl${replies.length === 1 ? "y" : "ies"}`}</p>
          </div></div>
        {replies.length > 0 && <div className="slack-thread" aria-label="Thread">
          {replies.map((c) => (
            <div key={c.id} className="slack-msg"><span className="slack-av">{c.by.split(" ").map((w) => w[0]).join("").slice(0, 2)}</span>
              <div><strong>{c.by}</strong> {c.by === "Lumen" ? <span className="slack-app">APP</span> : null} <span className="ds-muted">{time(c.at)}</span><p>{c.text}</p></div></div>))}
        </div>}
      </div>
      <p><Link className="ds-link" to="/centre/consume">{replies.length ? "Back to the Morning Note" : "Reply on the Morning Note"}</Link></p>
    </>
  );
}
