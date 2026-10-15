import { useCallback, useEffect, useState, type FormEvent, type ReactNode } from "react";
import { Link, useParams } from "react-router-dom";

import { ApiError, Refused, apiGet, apiSend } from "../api/client";
import { Button, CommentThread, EmptyState, Footnote, PageFrame, SideCard, Trail, VersionList, type Comment } from "../design";
import { nodeText as T } from "./nodeCopy";
import { kmText as K } from "./knowledgeMapCopy";
import { useOverview, type KEdge, type KNode } from "./knowledgeMap";
import { SHOWN_FOR, WhereBody } from "./WhereItLives";

// One thing on the map (Desk-Node artboard): where it came from, its definition, what people said, its versions and who may see the figure.
// An owner arrives from a Decide line on the pulse; anyone from the map. Anonymous comments carry "Anonymous" from the server and nothing else.

interface Step { step: string; label?: string; detail?: string; ref?: string; by?: string; at?: string }
interface Detail {
  id: string; type: string; label: string; owner: string | null; steward: string | null; trail: Step[];
  definition: { term: string; business: string; technical: string; process: string } | null;
  versions: { v: number; what: string; by: string; at: string }[]; commits: { id: string; when: string; what: string; by: string }[];
  baseline_id?: string | null; may_see_named?: number | null;
}
type Item = Comment & { line?: string };
interface Comments { comments: Item[]; may_decide: boolean }
type Kind = "suggestion" | "ambiguity" | "comment" | "ask";

const asDate = (iso: string | undefined | null) => {
  const d = iso ? new Date(iso) : null;
  return d && !Number.isNaN(d.getTime()) ? d : null;
};
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];  // "Sep", never the locale's "Sept"
const day = (iso: string | undefined | null) => { const d = asDate(iso); return d ? `${d.getDate()} ${MONTHS[d.getMonth()]}` : (iso ?? ""); };
/** "2 days ago", "last week", "3 weeks ago"; a date once it is older than two months. */
const ago = (iso: string | undefined | null) => {
  const d = asDate(iso);
  if (!d) return iso ?? "";
  const n = Math.floor((Date.now() - d.getTime()) / 86_400_000);
  return n < 1 ? "today" : n === 1 ? "yesterday" : n < 7 ? `${n} days ago` : n < 14 ? "last week" : n < 60 ? `${Math.floor(n / 7)} weeks ago` : day(iso);
};
const month = (iso: string | undefined | null) => asDate(iso)?.toLocaleDateString("en-GB", { month: "long", year: "numeric" }) ?? "";
/** A main-column card: the artboard's teal heading, with a right-hand note when given. */
function MainCard({ title, note, children }: { title: string; note?: string; children: ReactNode }) {
  return (
    <div className="ds-card ds-side">
      <div className="ds-side__head">
        <strong className="ds-side__title" style={{ color: "var(--ds-teal-bright)" }}>{title}</strong>
        {note && <span className="ds-muted" style={{ fontSize: 13 }}>{note}</span>}
      </div>
      {children}
    </div>
  );
}
const BODY = { fontSize: 15, lineHeight: 1.5 };
const first = (name: string | null | undefined) => (name ?? "").split(" ")[0];

export default function NodePage() {
  const { nodeId = "" } = useParams();
  const base = `/api/company/graph/node/${encodeURIComponent(nodeId)}`;
  const [d, setD] = useState<Detail | null | "missing">(null);
  const [list, setList] = useState<Comments | null | "failed">(null);
  const [kind, setKind] = useState<Kind | null>(null);
  const [text, setText] = useState("");
  const [anon, setAnon] = useState(false);
  const [note, setNote] = useState("");
  const [reply, setReply] = useState("");
  const [map, setMap] = useState<{ nodes: KNode[]; edges: KEdge[] } | "failed" | null>(null);
  const [scanAt, setScanAt] = useState(0);
  const ov = useOverview(scanAt);

  const loadComments = useCallback(() => apiGet<Comments>(`${base}/comments`).then(setList, () => setList("failed")), [base]);
  useEffect(() => {
    apiGet<Detail>(base).then(setD, () => setD("missing"));
    void loadComments();
    apiGet<{ nodes: KNode[]; edges: KEdge[] }>("/api/company/graph?view=map").then((g) => setMap(Array.isArray(g?.nodes) && Array.isArray(g?.edges) ? g : "failed"), () => setMap("failed"));
  }, [base, loadComments]);
  // an accepted suggestion becomes a new version: reload the versions and the version in the subline too
  const reloadDetail = () => apiGet<Detail>(base).then(setD, () => undefined);

  const open = (k: Kind) => { setKind(k); setText(""); setNote(""); setReply(""); };
  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!kind || !text.trim() || !d || d === "missing") return;
    setNote("");
    if (kind === "ask") {
      if (!d.baseline_id) { setReply(T.lensNoBaseline); return; }
      try {
        const r = await apiSend<{ text: string }>("POST", `/api/modules/m2_baseline/baselines/${d.baseline_id}/lens/ask`, { question: `${d.label}: ${text}` });
        setReply(r.text);
      } catch (err) { setReply(err instanceof Refused ? T.lensRefused : T.lensFailed); }
      return;
    }
    try {
      await apiSend("POST", `${base}/comments`, { kind, text, anonymous: anon });
      setKind(null);
      setText("");
      setAnon(false);
      await loadComments();
    } catch (err) { setNote(err instanceof ApiError ? err.message : T.saveFailed); }
  }
  async function decide(id: string, state: string, answer: string) {
    setNote("");
    try {
      await apiSend("POST", `${base}/comments/${id}/decide`, { state, answer });
      await Promise.all([loadComments(), reloadDetail()]);
    } catch (err) { setNote(err instanceof ApiError ? err.message : T.saveFailed); }
  }

  if (d === null || d === "missing") {
    return (
      <div className="ds-screen">
        <PageFrame title={d === null ? T.loadingTitle : T.missingTitle} crumbs={<Link className="ds-link" to="/centre/intent/graph">{T.mapCrumb}</Link>}>
          {d === null
            ? <EmptyState title={T.loadingTitle} lines={[T.loadingLine]} />
            : <EmptyState title={T.missingTitle} lines={[T.missingLine]} links={[{ label: T.backToMap, href: "/centre/intent/graph" }]} />}
        </PageFrame>
      </div>
    );
  }

  const current = d.versions.length ? Math.max(...d.versions.map((v) => v.v)) : null;
  const releasedIn = month(d.trail.find((s) => s.step === "released")?.at);
  const subline = [T.kind(d.type), current && T.version(current), d.owner && T.ownedBy(d.owner), d.steward && T.steward(d.steward),
    releasedIn && T.released(releasedIn)].filter(Boolean).join(" · ");
  const decider = first(d.owner ?? d.steward);
  // the server's state line ("Open · Olga to decide") travels in `line`; CommentThread shows its own until it reads `line` (see report)
  const comments = list && list !== "failed" ? list.comments.map((c) => ({ ...c, at: ago(c.at) })) : [];
  const form = kind ? T.form[kind] : null;
  const formTitle = kind === "ask" ? T.ask : kind === "suggestion" ? T.suggest : kind === "ambiguity" ? T.flag : T.addComment;

  return (
    <div className="ds-screen">
      <PageFrame
        crumbs={<><Link className="ds-link" to="/centre/intent/graph">{T.mapCrumb}</Link> / {T.plural(d.type)} / {d.label}</>}
        title={d.label}
        subline={subline}
        actions={<>
          <Button variant="primary" onClick={() => open("suggestion")}>{T.suggest}</Button>
          <Button onClick={() => open("ambiguity")}>{T.flag}</Button>
          <Button onClick={() => open("ask")}>{T.ask}</Button>
        </>}
      >
        <div className="ds-frame" style={{ padding: 0 }}>
        <div className="ds-frame__main">
        {form && (
          <form className="ds-card ds-side" onSubmit={submit}>
            <strong className="ds-side__title">{formTitle}</strong>
            <div className="ds-comment__decide">
              <input aria-label={form.label} placeholder={form.hint} value={text} onChange={(e) => setText(e.target.value)} />
              <Button type="submit" variant="primary" disabled={!text.trim()}>{kind === "ask" ? T.send : T.post}</Button>
              <Button onClick={() => setKind(null)}>{T.cancel}</Button>
            </div>
            {kind !== "ask" && <label className="ds-soft"><input type="checkbox" checked={anon} onChange={(e) => setAnon(e.target.checked)} /> {T.anonymous}</label>}
            {reply && <p className="ds-soft" aria-live="polite">{reply}</p>}
            {note && <p className="ds-warn" role="alert">{note}</p>}
          </form>
        )}

        <MainCard title={T.trailTitle}>
          <Trail steps={d.trail.map((s) => ({ step: s.step, label: s.label, ref: s.detail || undefined }))} />
        </MainCard>

        {SHOWN_FOR.includes(d.type) && (
          <MainCard title={K.where.title}>
            {map && map !== "failed"
              ? <WhereBody id={d.id} type={d.type} nodes={map.nodes} edges={map.edges} ov={ov === "failed" ? null : ov} onChanged={() => { setScanAt((n) => n + 1); void reloadDetail(); }} />
              : <p>{map === null ? T.loadingLine : K.panel.unavailable}</p>}
          </MainCard>
        )}

        <MainCard title={T.definitionTitle(current)}>
          {d.definition ? <>
            {d.definition.business && <div style={BODY}><b>{T.business}</b> {d.definition.business}</div>}
            {d.definition.technical && <div className="ds-soft" style={BODY}><b>{T.technical}</b> {d.definition.technical}</div>}
            {d.definition.process && <Footnote>{T.process(d.definition.process)}</Footnote>}
          </> : <p>{T.noDefinition}</p>}
        </MainCard>

        <MainCard title={T.commentsTitle(comments.length)} note={decider ? T.toPulse(decider) : undefined}>
          {list === "failed" ? <p className="ds-warn">{T.commentsFailed}</p>
            : list === null ? <p className="ds-muted">{T.loadingLine}</p>
            : comments.length === 0 ? <p>{T.noComments}</p>
            : <CommentThread comments={comments} canDecide={list.may_decide} onDecide={(id, s, a) => void decide(id, s, a)} />}
          {note && !form && <p className="ds-warn" role="alert">{note}</p>}
          <div><Button onClick={() => open("comment")}>{T.addComment}</Button></div>
        </MainCard>
        </div>
        <div className="ds-frame__aside">

          <SideCard title={T.versionsTitle}>
            {d.versions.length ? <VersionList versions={d.versions.map((v) => ({ ...v, at: day(v.at) }))} /> : <p>{T.noVersions}</p>}
          </SideCard>
          {(d.type === "Measure" || d.commits.length > 0) && (
            <SideCard title={T.commitsTitle}>
              {d.commits.length ? (
                <div className="ds-versions">
                  {d.commits.map((c) => <div key={c.id}><span className="ds-muted">{c.id} · {day(c.when)}</span> · {c.what} · {c.by}</div>)}
                </div>
              ) : <p>{T.noCommits}</p>}
            </SideCard>
          )}
          {d.type === "Measure" && (
            <SideCard title={T.seeTitle}><p>{d.may_see_named ? T.seeNamed(d.may_see_named) : T.seeNobody}</p></SideCard>
          )}
        </div>
        </div>
      </PageFrame>
    </div>
  );
}
