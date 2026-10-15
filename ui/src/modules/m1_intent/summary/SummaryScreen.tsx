import { Link, useParams } from "react-router-dom";

import Panel from "../../../components/Panel";
import ScreenState from "../../../components/ScreenState";
import { getSummary, type SummaryNote, type SummaryPage } from "../api";
import CharterPaper from "../CharterPaper";
import ShareCharter from "../charter/ShareCharter";
import { m1Charter as C, m1Summary as T } from "../copy";
import { useLoad } from "../useLoad";

const when = (iso: string) => new Date(iso).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" });
const PRINT = "@media print { .no-print { display: none !important; } .m1-summary-page .n-panel { break-inside: avoid; box-shadow: none; } }";

/** Who wrote a note: "an anonymous note", the name, or nothing when a named note has no name on it. */
function Author({ anonymous, name }: { anonymous: boolean; name?: string }) {
  const who = anonymous ? T.anonymousNote : name;
  return who ? <span className="n-muted">({who})</span> : null;
}

/** One kind of note (pain points, signals to track, levers): its words, and its own fields when the room filled them in. */
function NoteList({ title, rows }: { title: string; rows: SummaryNote[] }) {
  return (
    <Panel title={title}>
      {rows.length === 0 ? (
        <p className="state n-muted">{T.none}</p>
      ) : (
        <ul>
          {rows.map((n, i) => (
            <li key={i}>
              {n.text} <Author anonymous={n.anonymous} name={n.author_name} />
              {n.details.map((d) => <div key={d.label} className="n-e1-def-note">{`${d.label}: ${d.values.join("; ")}`}</div>)}
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}

function Contributions({ c }: { c: SummaryPage["contributions"] }) {
  return (
    <Panel title={T.contributed}>
      <p className="n-e1-def-note">{T.totals(c.totals.notes, c.totals.comments, c.totals.votes)}</p>
      {c.people === null ? (
        <p className="n-e1-def-note">{c.small_group ? T.smallGroup : T.anonymousHidden}</p>
      ) : (
        <table className="n-table">
          <thead>
            <tr>
              <th scope="col">{T.colPerson}</th>
              <th scope="col">{T.colNotes}</th>
              <th scope="col">{T.colComments}</th>
              <th scope="col">{T.colVotes}</th>
            </tr>
          </thead>
          <tbody>
            {c.people.map((p, i) => (
              <tr key={i}>
                <th scope="row">{p.role ? `${p.name} (${p.role})` : p.name}</th>
                <td>{p.notes}</td>
                <td>{p.comments}</td>
                <td>{p.votes}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {c.anonymous ? <p>{T.anonymousTotal(c.anonymous.total)}</p> : null}
    </Panel>
  );
}

/** The page people open after the session: the same views as the board and the charter, drawn once, read-only and printable. */
export default function SummaryScreen({ sessionId: given }: { sessionId?: string } = {}) {
  const params = useParams();
  const sessionId = given ?? params.sessionId ?? "";
  const { state, data, message, retry } = useLoad<SummaryPage>(() => getSummary(sessionId), `summary:${sessionId}`);
  const d = data;
  return (
    <ScreenState state={state} message={message ?? (state === "error" ? T.loadFailed : undefined)} onRetry={retry}>
      {d ? (
        <div className="m1-summary-page" style={{ display: "grid", gap: 16 }}>
          <style>{PRINT}</style>
          <Panel
            title={d.session.title || T.title}
            eyebrow={T.eyebrow}
            actions={
              <button type="button" className="n-btn no-print" onClick={() => window.print()}>
                {T.print}
              </button>
            }
          >
            <p className="n-e1-def-note">{`${T.session}: ${d.session.date} · ${T.took(d.session.people_count)}`}</p>
            <ul>
              {d.session.people.map((p, i) => (
                <li key={i}>{p.role ? `${p.name}, ${p.role}` : p.name}</li>
              ))}
            </ul>
          </Panel>

          <Panel title={T.intent}>
            <p className="n-e1-def-note">{T.intentHelp}</p>
            {d.intent.map((g) => (
              <div key={g.id}>
                <h3>{g.label}</h3>
                {g.items.length === 0 ? (
                  <p className="state n-muted">{T.none}</p>
                ) : (
                  <ul>
                    {g.items.map((i) => (
                      <li key={i.id}>{`${i.name} · ${T.boardNotes(i.note_count)} · ${T.votes(i.vote_total)}`}</li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
          </Panel>

          <NoteList title={T.painPoints} rows={d.pain_points} />
          <NoteList title={T.future} rows={d.future_signals} />
          <NoteList title={T.levers} rows={d.levers} />

          <Panel title={T.board}>
            {d.board.clusters.length === 0 ? (
              <p className="state n-muted">{T.none}</p>
            ) : (
              d.board.clusters.map((c) => (
                <div key={c.id}>
                  <h3>{`${c.name} · ${T.boardNotes(c.notes.length)}`}</h3>
                  <ul>
                    {c.notes.map((n) => (
                      <li key={n.id}>
                        {n.text} <Author anonymous={n.anonymous} name={n.author_name} />
                      </li>
                    ))}
                  </ul>
                </div>
              ))
            )}
          </Panel>

          {d.charter ? (
            <CharterPaper doc={d.charter} status={d.charter.status}>
              {d.charter.signing.signers.map((s, i) => (
                <p key={i} className="n-e1-def-note">
                  {C.signedBy(s.name, when(s.at), s.how)}
                </p>
              ))}
              {d.can_download ? (
                <div className="no-print">
                  <ShareCharter sessionId={sessionId} organiser={false} />
                </div>
              ) : null}
            </CharterPaper>
          ) : (
            <Panel title={T.charter}>
              <p className="state n-muted">{T.noCharter}</p>
            </Panel>
          )}

          <Contributions c={d.contributions} />
        </div>
      ) : null}
    </ScreenState>
  );
}

/** The way to the summary, from the screens that show the charter and from the closing screen. */
export function SummaryLink({ sessionId }: { sessionId: string }) {
  return (
    <p className="no-print">
      <Link className="n-btn" to={`/modules/m1_intent/sessions/${encodeURIComponent(sessionId)}/summary`}>
        {T.link}
      </Link>{" "}
      <span className="n-e1-def-note">{T.linkHelp}</span>
    </p>
  );
}
