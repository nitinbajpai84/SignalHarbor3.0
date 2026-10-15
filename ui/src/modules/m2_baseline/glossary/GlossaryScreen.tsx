import { useState } from "react";
import { useParams } from "react-router-dom";

import { ApiError } from "../../../api/client";
import DownloadButton from "../../../components/DownloadButton";
import PageHead from "../../../components/PageHead";
import Panel from "../../../components/Panel";
import ScreenState, { type ScreenStateName } from "../../../components/ScreenState";
import StatusPill from "../../../components/StatusPill";
import { useLoad } from "../../m1_intent/useLoad";
import PersonalNotice from "../agents/PersonalNotice";
import BaselineSteps from "../BaselineSteps";
import { m2Gloss as t } from "./copy";
import {
  buildGlossary,
  decideEntry,
  getGlossary,
  glossaryExcelUrl,
  glossaryPrintUrl,
  reviewEntry,
  reviewUnchanged,
  uploadGlossary,
  type Choice,
  type GlossaryChange,
  type GlossaryEntry,
  type GlossaryView,
} from "./glossaryApi";

type Filter = "all" | GlossaryChange;
const FILTERS: Filter[] = ["all", "changed", "new", "unchanged"];
const TONE = { changed: "warning", new: "info", unchanged: "success" } as const;
const readBase64 = (file: File): Promise<string> =>
  new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve(String(r.result).split(",")[1] ?? "");
    r.onerror = () => reject(new Error("read"));
    r.readAsDataURL(file);
  });

/** M2-E2: the business glossary, with your own glossary beside it. Existing versus new, a filter, a decision per entry, review, downloads. */
export default function GlossaryScreen() {
  const { baselineId = "" } = useParams();
  const loaded = useLoad(() => getGlossary(baselineId), `m2-glossary-${baselineId}`, (g) => !g.built && g.entries.length === 0);
  const [fresh, setFresh] = useState<GlossaryView | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<Filter>("all");
  const [file, setFile] = useState<File | null>(null);
  const view = fresh ?? loaded.data;
  const state: ScreenStateName = fresh ? (fresh.built || fresh.entries.length > 0 ? "populated" : "empty") : loaded.state;
  const locked = view?.signed === true;

  const run = async (what: string, call: () => Promise<GlossaryView>, done?: string) => {
    setBusy(what);
    setError(null);
    setNote(null);
    try {
      const v = await call();
      setFresh(v);
      setNote([done, v.lens_note, v.note].filter(Boolean).join(" ") || null);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : t.failed);
    } finally {
      setBusy(null);
    }
  };

  const actions = (
    <>
      <button type="button" className="n-btn" disabled={busy !== null || locked} onClick={() => void run("build", () => buildGlossary(baselineId), t.built)}>
        {busy === "build" ? t.building : t.build}
      </button>
      <DownloadButton primary path={glossaryExcelUrl(baselineId)} fallbackName="glossary.xlsx" label={t.downloadExcel} />
      <DownloadButton path={glossaryPrintUrl(baselineId)} fallbackName="glossary.html" label={t.downloadPrint} />
    </>
  );

  return (
    <>
      <PageHead eyebrow={t.eyebrow} title={t.title} sub={t.sub} actions={state === "refused" ? undefined : actions} />
      <BaselineSteps baselineId={baselineId} signed={locked} />
      {note ? <p role="status">{note}</p> : null}
      {(view?.personal_documents ?? []).map((d) => (
        <PersonalNotice key={d.doc_id} baselineId={baselineId} docId={d.doc_id} title={view?.provided?.title ?? t.title} words={d.personal_words} restrictPath={d.restrict_path}
          onDecided={() => void run("refresh", () => getGlossary(baselineId))} />
      ))}
      {error ? (
        <p role="alert" className="state state-error">
          {error}
        </p>
      ) : null}
      {state === "populated" || state === "empty" ? (
        <Panel title={t.uploadTitle}>
          <p className="n-muted">{t.uploadHelp}</p>
          <fieldset disabled={locked || busy !== null} style={{ border: 0, padding: 0, margin: 0, minWidth: 0 }}>
            <label className="n-field">
              {t.uploadLabel}
              <input type="file" accept=".xlsx,.csv,.md,.txt,.docx" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
            </label>
            <button
              type="button"
              className="n-btn"
              disabled={!file}
              onClick={() => file && void run("upload", async () => uploadGlossary(baselineId, file.name, await readBase64(file)))}
            >
              {busy === "upload" ? t.uploading : t.upload}
            </button>
          </fieldset>
        </Panel>
      ) : null}
      <ScreenState state={state} message={state === "empty" ? t.empty : loaded.message} onRetry={loaded.retry}>
        {view ? <Loaded view={view} filter={filter} setFilter={setFilter} locked={locked} busy={busy} baselineId={baselineId} run={run} /> : null}
      </ScreenState>
    </>
  );
}

interface LoadedProps {
  view: GlossaryView;
  filter: Filter;
  setFilter: (f: Filter) => void;
  locked: boolean;
  busy: string | null;
  baselineId: string;
  run: (what: string, call: () => Promise<GlossaryView>, done?: string) => Promise<void>;
}

function Loaded({ view, filter, setFilter, locked, busy, baselineId, run }: LoadedProps) {
  const rows = view.entries.filter((e) => filter === "all" || e.change === filter);
  const news = view.entries.filter((e) => e.change === "new");
  return (
    <>
      <p className="n-muted">{view.provided ? t.provided(view.provided.title, view.provided.by, view.provided.at.slice(0, 10)) : t.noneProvided}</p>
      {view.restricted_kept ? <p role="status">{t.restrictedKept(view.restricted_kept)}</p> : null}
      {view.waiting > 0 ? <p role="status">{t.waiting(view.waiting)}</p> : null}
      <Panel>
        <div className="n-flex wrap">
          <span id="gloss-filter">{t.filterLabel}</span>
          <div role="group" aria-labelledby="gloss-filter" className="n-flex wrap">
            {FILTERS.map((f) => (
              <button key={f} type="button" className={`n-btn${filter === f ? " primary" : ""}`} aria-pressed={filter === f} onClick={() => setFilter(f)}>
                {t.filters[f]} ({view.counts[f]})
              </button>
            ))}
          </div>
          <span className="n-muted">{t.progress(view.counts.reviewed, view.counts.all)}</span>
          <button type="button" className="n-btn" disabled={locked || busy !== null || view.counts.unchanged === 0} onClick={() => void run("review", () => reviewUnchanged(baselineId))}>
            {t.reviewAllUnchanged}
          </button>
        </div>
        {rows.length === 0 ? (
          <p className="n-muted">{t.nothingShown}</p>
        ) : (
          <table className="n-table">
            <thead>
              <tr>
                <th scope="col">{t.cols.term}</th>
                <th scope="col">{t.cols.previous}</th>
                <th scope="col">{t.cols.current}</th>
                <th scope="col">{t.cols.assumption}</th>
                <th scope="col">{t.cols.decide}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((e) => (
                <Row key={e.kpi_id} e={e} locked={locked} busy={busy} baselineId={baselineId} run={run} />
              ))}
            </tbody>
          </table>
        )}
      </Panel>
      {view.provided ? (
        <>
          <Panel title={t.unmatchedTitle}>
            {view.unmatched_terms.length === 0 ? (
              <p className="n-muted">{t.unmatchedNone}</p>
            ) : (
              <ul>
                {view.unmatched_terms.map((u, i) => (
                  <li key={`${i}-${u.term}`}>
                    <strong>{u.term}</strong>
                    {u.definition ? `: ${u.definition}` : ""}
                  </li>
                ))}
              </ul>
            )}
          </Panel>
          <Panel title={t.newTitle}>
            {news.length === 0 ? (
              <p className="n-muted">{t.newNone}</p>
            ) : (
              <ul>
                {news.map((e) => (
                  <li key={e.kpi_id}>{e.text.term}</li>
                ))}
              </ul>
            )}
          </Panel>
        </>
      ) : null}
    </>
  );
}

interface RowProps {
  e: GlossaryEntry;
  locked: boolean;
  busy: string | null;
  baselineId: string;
  run: LoadedProps["run"];
}

function Row({ e, locked, busy, baselineId, run }: RowProps) {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(e.text.definition === "Not available yet" ? "" : e.text.definition);
  const off = locked || busy !== null;
  const decide = (choice: Choice, words?: string) => run("decide", () => decideEntry(baselineId, e.kpi_id, choice, words)).then(() => setEditing(false));
  return (
    <tr>
      <th scope="row">
        {e.text.term} <StatusPill tone={TONE[e.change]}>{e.text.change}</StatusPill>
        {e.text.aliases ? <div className="n-muted">{t.alsoCalled(e.text.aliases)}</div> : null}
        {e.match === "meaning" ? <div className="n-muted">{t.matchedByMeaning}</div> : null}
      </th>
      <td>{e.text.previous === "Not available yet" ? <span className="n-muted">{t.noPrevious}</span> : e.text.previous}</td>
      <td>
        {e.text.definition}
        <div className="n-muted">{e.text.how_sure}</div>
        {e.proposal ? <div className="n-muted">{t.proposal(e.text.proposal)}</div> : null}
      </td>
      <td>
        {e.assumption}
        {e.source_document ? <div className="n-muted">{t.from(e.source_document)}</div> : null}
      </td>
      <td>
        <div className="n-muted">{e.reviewed ? t.reviewedBy(e.text.reviewed) : t.notReviewed}</div>
        {e.decided ? <div className="n-muted">{t.decidedBy(e.text.decided_by)}</div> : null}
        {editing ? (
          <div>
            <label className="n-field">
              {t.editLabel}
              <textarea value={text} rows={3} maxLength={2000} onChange={(ev) => setText(ev.target.value)} />
            </label>
            <button type="button" className="n-btn primary" disabled={off || !text.trim()} onClick={() => void decide("edited", text)}>
              {t.save}
            </button>
            <button type="button" className="n-btn" onClick={() => setEditing(false)}>
              {t.cancel}
            </button>
          </div>
        ) : (
          <div className="n-flex wrap">
            <button type="button" className="n-btn" disabled={off || e.text.definition === "Not available yet"} onClick={() => void decide("ours")}>
              {t.keepOurs}
            </button>
            <button type="button" className="n-btn" disabled={off || e.text.previous === "Not available yet"} onClick={() => void decide("provided")}>
              {t.keepProvided}
            </button>
            {e.matched_term ? (
              <button type="button" className="n-btn" disabled={off} onClick={() => void decide("not_same")}>
                {t.notSame}
              </button>
            ) : null}
            <button type="button" className="n-btn" disabled={off} onClick={() => setEditing(true)}>
              {t.edit}
            </button>
            {!e.reviewed ? (
              <button type="button" className="n-btn" disabled={off} onClick={() => void run("review", () => reviewEntry(baselineId, e.kpi_id))}>
                {t.markReviewed}
              </button>
            ) : null}
          </div>
        )}
      </td>
    </tr>
  );
}
