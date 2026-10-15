import { useState } from "react";
import { useSearchParams } from "react-router-dom";

import { ApiError, apiGet, apiSend } from "../../api/client";
import DownloadButton from "../../components/DownloadButton";
import Panel from "../../components/Panel";
import ScreenState from "../../components/ScreenState";
import { useLoad } from "../../components/useLoad";
import { Button, Chip, Pill } from "../../design";
import { BASE } from "../../modules/m2_baseline/api";
import {
  buildGlossary,
  decideEntry,
  getGlossary,
  glossaryExcelUrl,
  glossaryPrintUrl,
  reviewUnchanged,
  uploadGlossary,
  type Choice,
  type GlossaryEntry,
  type GlossaryView,
} from "../../modules/m2_baseline/glossary/glossaryApi";
import { acceptAmbiguity, answerAmbiguity, type Ambiguity } from "../../modules/m2_baseline/technical/technicalApi";
import { useSession } from "../../useSession";

// Spec 29: the Glossary tab in Define's right panel (Screen A), the owner's "Confirm my terms" (?view=mine, Screen B) and the
// governance lead's ambiguities (?view=ambiguities, Screen C). The terms stay in the m2_baseline glossary the Initiative points at.

const t = {
  title: "Business glossary",
  empty: "No terms yet. Lens drafts them when the wall closes.",
  noBaseline: "Not available yet. This Initiative has no baseline for Lens to draft into.",
  draftNow: "Ask Lens to draft now",
  drafting: "Lens is drafting",
  update: "Update draft",
  sources: "Not available yet. Sources not counted.",
  upload: "Upload your own glossary",
  uploadHint: "Optional. Lens will also match against the company's terms.",
  noMatch: "No term matches",
  noMatchFilter: "No term matches this filter",
  search: "Search terms",
  reused: "Reused from the company",
  noWording: "Not available yet. No source gave a wording.",
  noSource: "No source. Added by hand.",
  noOwner: "No owner yet. Lens asks the sponsor.",
  oneMeaning: "One meaning found.",
  edit: "Edit wording",
  save: "Save wording",
  ours: "Keep Lens's wording",
  provided: "Keep the provided wording",
  notSame: "Not the same term",
  useIt: "Use it",
  dismiss: "Dismiss",
  confirmUnchanged: "Confirm all unchanged",
  noUnchanged: "No unchanged terms waiting",
  excel: "Download Excel",
  print: "Printable page",
  back: "Back",
  closedForRole: "Not available yet. The terms open to the organiser, the analyst, the sponsor and the company admin until owners can sign in to them.",
  failed: "That did not work. Please try again.",
  // Screen B
  nothingWaiting: "Nothing waiting for you.",
  backToInitiative: "Back to the Initiative",
  mineRight: "Mine, wording is right",
  mineChange: "Mine, change the wording",
  notMine: "Not mine, it is",
  notMineIdk: "I do not know",
  notMinePick: "Who owns it",
  sent: "Done.",
  askLater: "Ask me later",
  suggestion: "Suggestion",
  useSuggestion: "Use the suggestion",
  bothUsed: "Both are used, send to the governance lead",
  bothNote: "A note for the governance lead (optional)",
  // Screen C
  noAmbiguities: "No ambiguous terms. Every term has one meaning.",
  pickMeaning: "Pick one meaning",
  keepBoth: "Keep both, name the second term",
  secondName: "Name of the second term",
  accept: "Accept as a known risk",
  reason: "Why you accept it",
  reasonRequired: "A reason is required",
  reopen: "Reopen",
  reopenWhy: "Why you reopen it",
  meanings: "Meanings found",
} as const;

const CHIPS = ["All", "Draft", "Confirmed", "Ambiguous", "Accepted as risk", "Reused", "Mine"] as const;
type ChipName = (typeof CHIPS)[number];
const EDITORS = ["company_admin", "analyst", "sponsor"];

interface StartTerm { term: string; term_id?: string; restricted: boolean }
interface Start {
  intent_id: string;
  baseline_id: string | null;
  terms: StartTerm[];
  counts: Record<string, number> | null;
  questions_left: number | null;
  ambiguities?: Ambiguity[];
  people?: { display_name: string }[];
  can_settle?: boolean;
}
interface Ambs { ambiguities: Ambiguity[] }

const readBase64 = (file: File): Promise<string> =>
  new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve(String(r.result).split(",")[1] ?? "");
    r.onerror = () => reject(new Error("read"));
    r.readAsDataURL(file);
  });
const norm = (s: string | null | undefined) => (s ?? "").trim().toLowerCase().replace(/\s+/g, " ");
const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;

interface Data { start: Start; view: GlossaryView | null; ambs: Ambiguity[]; closed: boolean }

async function load(intentId: string): Promise<Data> {
  const start = await apiGet<Start>(`/api/intents/${encodeURIComponent(intentId)}/glossary-start`);
  if (!start.baseline_id) return { start, view: null, ambs: [], closed: false };
  try {
    const [view, a] = await Promise.all([
      getGlossary(start.baseline_id),
      apiGet<Ambs>(`${BASE}/baselines/${encodeURIComponent(start.baseline_id)}/ambiguities`).catch(() => ({ ambiguities: start.ambiguities ?? [] })),
    ]);
    return { start, view, ambs: a.ambiguities, closed: false };
  } catch (e) {
    if (e instanceof ApiError && e.status === 403) return { start, view: null, ambs: [], closed: true };
    throw e;
  }
}

/** The Glossary tab body. B13's Define view mounts it with the intent id; `?view=mine|ambiguities` picks Screen B or C. */
export function GlossaryTab({ intentId }: { intentId: string }) {
  const [params] = useSearchParams();
  const loaded = useLoad(() => load(intentId), `ic-glossary-${intentId}`);
  const [fresh, setFresh] = useState<Data | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const data = fresh ?? loaded.data;

  const run = async (what: string, call: () => Promise<unknown>) => {
    setBusy(what);
    setError(null);
    try {
      await call();
      setFresh(await load(intentId));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : t.failed);
    } finally {
      setBusy(null);
    }
  };

  const which = params.get("view");
  return (
    <div className="ic-glossary">
      {error ? <p role="alert" className="state state-error">{error}</p> : null}
      <ScreenState state={fresh ? "populated" : loaded.state} message={loaded.message} onRetry={loaded.retry}>
        {data ? (
          which === "mine" ? <Mine data={data} busy={busy} run={run} intentId={intentId} />
            : which === "ambiguities" ? <Settle data={data} busy={busy} run={run} intentId={intentId} />
              : <TermList data={data} busy={busy} run={run} />
        ) : null}
      </ScreenState>
    </div>
  );
}

type Run = (what: string, call: () => Promise<unknown>) => Promise<void>;

/** The owner's and the settler's replies (spec 29 Screens B and C): one route, an action in the body. */
const reply = (intentId: string, kpi: string, body: Record<string, string>) =>
  apiSend("POST", `/api/intents/${encodeURIComponent(intentId)}/glossary/${encodeURIComponent(kpi)}/reply`, body);

function ambsOf(ambs: Ambiguity[], kpi: string) {
  return ambs.filter((a) => a.kpi_id === kpi);
}

function stateOf(e: GlossaryEntry, ambs: Ambiguity[]): string {
  const mine = ambsOf(ambs, e.kpi_id);
  if (mine.some((a) => a.status === "accepted")) return "Accepted as risk";
  if (mine.some((a) => a.status === "open")) return "Ambiguous";
  return e.reviewed ? "Confirmed" : "Draft";
}

function Header({ data, busy, run }: { data: Data; busy: string | null; run: Run }) {
  const { user } = useSession();
  const can = (user?.roles ?? []).some((r) => EDITORS.includes(r));
  const { view, start, ambs } = data;
  const bid = start.baseline_id;
  const [file, setFile] = useState<File | null>(null);
  const total = view ? view.entries.length + view.unmatched_terms.length : 0;
  const accepted = view ? view.entries.filter((e) => stateOf(e, ambs) === "Accepted as risk").length : 0;
  const confirmed = view?.counts.reviewed ?? 0;
  const built = !!view && (view.built || total > 0);
  const locked = view?.signed === true;
  return (
    <Panel title={t.title}>
      {built ? (
        <p>{`${plural(total, "term", "terms")}: ${confirmed} confirmed, ${total - confirmed - accepted} draft, ${accepted} ambiguous accepted`}</p>
      ) : (
        <p>{bid ? (data.closed ? t.closedForRole : t.empty) : t.noBaseline}</p>
      )}
      {built ? <p className="n-muted">{t.sources}</p> : null}
      {can && bid && !data.closed ? (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 8 }}>
          <Button variant="primary" disabled={busy !== null || locked} onClick={() => void run("build", () => buildGlossary(bid))}>
            {busy === "build" ? t.drafting : built ? t.update : t.draftNow}
          </Button>
          <label className="n-field" style={{ minWidth: 0 }}>
            {t.upload}
            <input type="file" accept=".xlsx,.csv,.md,.txt,.docx" disabled={locked} onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
          </label>
          <Button disabled={!file || busy !== null || locked}
            onClick={() => file && void run("upload", async () => uploadGlossary(bid, file.name, await readBase64(file)))}>{t.upload}</Button>
          <p className="n-muted" style={{ flexBasis: "100%", margin: 0 }}>{t.uploadHint}</p>
        </div>
      ) : null}
    </Panel>
  );
}

function TermList({ data, busy, run }: { data: Data; busy: string | null; run: Run }) {
  const { user } = useSession();
  const me = norm(user?.display_name);
  const [chip, setChip] = useState<ChipName>("All");
  const [q, setQ] = useState("");
  const [open, setOpen] = useState<string | null>(null);
  const { view, start, ambs } = data;
  const company = new Set(start.terms.filter((x) => !x.restricted).map((x) => norm(x.term)));
  const reused = (e: GlossaryEntry) => !!e.matched_term && company.has(norm(e.matched_term));
  const mine = (e: GlossaryEntry) => !!me && norm(e.text.owner) === me;
  const entries = view?.entries ?? [];
  const keep = (e: GlossaryEntry) => {
    const s = stateOf(e, ambs);
    const byChip = chip === "All" || (chip === "Reused" ? reused(e) : chip === "Mine" ? mine(e) : s === chip);
    const hay = norm(`${e.text.term} ${e.text.aliases}`);
    return byChip && (!q || hay.includes(norm(q)));
  };
  const shown = entries.filter(keep);
  const current = entries.find((e) => e.kpi_id === open);
  const editor = (user?.roles ?? []).some((r) => EDITORS.includes(r));
  const unchanged = entries.filter((e) => e.change === "unchanged" && !e.reviewed).length;
  const bid = start.baseline_id ?? "";

  return (
    <>
      <Header data={data} busy={busy} run={run} />
      {view && entries.length > 0 ? (
        current ? (
          <Drawer e={current} ambs={ambsOf(ambs, current.kpi_id)} bid={bid} busy={busy} run={run} reused={reused(current)}
            canEdit={editor || mine(current)} owner={mine(current)} locked={view.signed} onBack={() => setOpen(null)} />
        ) : (
          <Panel>
            <div role="group" aria-label="Filter terms" style={{ display: "flex", gap: 6, overflowX: "auto", paddingBottom: 4 }}>
              {CHIPS.map((c) => {
                const n = c === "Mine" ? entries.filter(mine).length : null;
                return c === "Mine" && n === 0 ? (
                  <span key={c} className="ds-chip" aria-disabled="true" style={{ opacity: 0.5 }}>Mine 0</span>
                ) : (
                  <Chip key={c} tone={chip === c ? "active" : "default"} onClick={() => setChip(c)}>{n === null ? c : `${c} ${n}`}</Chip>
                );
              })}
            </div>
            <label className="n-field">
              {t.search}
              <input type="search" value={q} onChange={(e) => setQ(e.target.value)} />
            </label>
            {shown.length === 0 ? <p className="n-muted">{q ? t.noMatch : t.noMatchFilter}</p> : (
              <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
                {shown.map((e) => {
                  const open_ = ambsOf(ambs, e.kpi_id).filter((a) => a.status === "open").length;
                  return (
                    <li key={e.kpi_id} style={{ borderTop: "1px solid var(--line, #e5e5e5)", padding: "8px 0" }}>
                      <button type="button" className="ds-link" onClick={() => setOpen(e.kpi_id)}
                        style={{ background: "none", border: 0, padding: 0, textAlign: "left", cursor: "pointer", width: "100%" }}>
                        <strong>{e.text.term}</strong>{e.text.aliases ? <span className="n-muted"> ({e.text.aliases})</span> : null}
                        <span style={{ display: "block", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{e.text.definition}</span>
                        <span className="n-muted">{e.text.owner}</span>{" "}
                        <Pill tone={e.reviewed ? "ok" : "draft"}>{stateOf(e, ambs)}</Pill>
                        {open_ ? <> <Pill tone="late">{plural(open_, "meaning question", "meaning questions")} open</Pill></> : null}
                        {reused(e) ? <> <Pill tone="signed">{t.reused}</Pill></> : null}
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 12 }}>
              {editor ? (
                <Button disabled={!unchanged || busy !== null || view.signed} onClick={() => void run("unchanged", () => reviewUnchanged(bid))}>
                  {unchanged ? `${t.confirmUnchanged} (${unchanged})` : t.noUnchanged}
                </Button>
              ) : null}
              {editor ? <DownloadButton path={glossaryExcelUrl(bid)} fallbackName="glossary.xlsx" label={t.excel} /> : null}
              {editor ? <DownloadButton path={glossaryPrintUrl(bid)} fallbackName="glossary.html" label={t.print} /> : null}
            </div>
          </Panel>
        )
      ) : null}
    </>
  );
}

function Drawer({ e, ambs, bid, busy, run, reused, canEdit, owner, locked, onBack }: {
  e: GlossaryEntry; ambs: Ambiguity[]; bid: string; busy: string | null; run: Run; reused: boolean; canEdit: boolean; owner: boolean; locked: boolean; onBack: () => void;
}) {
  const [text, setText] = useState<string | null>(null);
  const decide = (choice: Choice, words?: string) => run(choice, () => decideEntry(bid, e.kpi_id, choice, words));
  const off = busy !== null || locked || !canEdit;
  const hasDef = e.text.definition && e.business_definition.value;
  return (
    <Panel title={e.text.term} actions={<Button onClick={onBack}>{t.back}</Button>}>
      {reused ? <Pill tone="signed">{t.reused}</Pill> : null}
      <h3>Definition</h3>
      <p>{hasDef ? e.text.definition : t.noWording}</p>
      {hasDef ? <p className="n-muted">{e.text.how_sure.replace("A guess (Lens)", "A guess by Lens")}</p> : null}
      {e.previous.value ? <p className="n-muted">Provided wording: {e.text.previous}</p> : null}
      {e.proposal?.value ? (
        <div className="ds-strip" role="note">
          <p>Lens has a newer draft: {e.proposal.value}</p>
          <Button disabled={off} onClick={() => void decide("edited", e.proposal?.value ?? "")}>{t.useIt}</Button>{" "}
          <Button disabled={off} onClick={() => void decide("ours")}>{t.dismiss}</Button>
        </div>
      ) : null}
      <h3>Source</h3>
      <p>{e.source_document || e.text.source || t.noSource}</p>
      <h3>Owner</h3>
      <p>{e.text.owner && e.text.owner !== "Not available yet" ? e.text.owner : t.noOwner}</p>
      <h3>{t.meanings}</h3>
      {ambs.length ? (
        <ul>{ambs.map((a) => <li key={a.id}>{a.text}{a.where ? <span className="n-muted"> ({a.where})</span> : null}</li>)}</ul>
      ) : <p className="n-muted">{t.oneMeaning}</p>}
      {canEdit ? (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
          {text === null ? (
            <Button disabled={off || (!!e.reviewed && !owner)} onClick={() => setText(e.text.definition)}>{t.edit}</Button>
          ) : (
            <>
              <label className="n-field" style={{ flexBasis: "100%" }}>
                {t.edit}
                <textarea maxLength={2000} rows={4} value={text} onChange={(x) => setText(x.target.value)} />
              </label>
              <Button variant="primary" disabled={off || !text.trim()} onClick={() => void decide("edited", text).then(() => setText(null))}>{t.save}</Button>
            </>
          )}
          {hasDef ? <Button disabled={off} onClick={() => void decide("ours")}>{t.ours}</Button> : null}
          {e.previous.value ? <Button disabled={off} onClick={() => void decide("provided")}>{t.provided}</Button> : null}
          {e.match ? <Button disabled={off} onClick={() => void decide("not_same")}>{t.notSame}</Button> : null}
        </div>
      ) : null}
    </Panel>
  );
}

function Mine({ data, busy, run, intentId }: { data: Data; busy: string | null; run: Run; intentId: string }) {
  const { user } = useSession();
  const me = norm(user?.display_name);
  const [skipped, setSkipped] = useState<string[]>([]);
  const [text, setText] = useState<string | null>(null);
  const [who, setWho] = useState("");
  const [note, setNote] = useState("");
  const bid = data.start.baseline_id ?? "";
  const people = (data.start.people ?? []).map((p) => p.display_name).filter((n) => norm(n) !== me);
  const mine = (data.view?.entries ?? []).filter((e) => me && norm(e.text.owner) === me && !e.reviewed);
  const left = mine.filter((e) => !skipped.includes(e.kpi_id));
  const e = left[0];
  const qLeft = data.start.questions_left;
  if (!e) {
    return (
      <Panel>
        <p>{data.closed ? t.closedForRole : t.nothingWaiting}</p>
        <a href={`/centre/intent/${encodeURIComponent(intentId)}`}>{t.backToInitiative}</a>
      </Panel>
    );
  }
  const q = ambsOf(data.ambs, e.kpi_id).find((a) => a.status === "open");
  const off = busy !== null || data.view?.signed === true;
  return (
    <div style={{ maxWidth: 640, margin: "0 auto" }}>
      <p>{`Term ${mine.length - left.length + 1} of ${mine.length}.`}{qLeft === null ? "" : ` You have ${plural(qLeft, "question", "questions")} left of 3.`}</p>
      <Panel title={e.text.term}>
        <p>{e.text.definition || t.noWording}</p>
        <p className="n-muted">{e.source_document || t.noSource}</p>
        <p className="n-muted">Owner: you</p>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
          <Button variant="primary" disabled={off || !e.business_definition.value} onClick={() => void run("ours", () => reply(intentId, e.kpi_id, { action: "mine" }))}>{t.mineRight}</Button>
          {text === null ? <Button disabled={off} onClick={() => setText(e.text.definition)}>{t.mineChange}</Button> : null}
          <Button disabled={off} onClick={() => setSkipped([...skipped, e.kpi_id])}>{t.askLater}</Button>
        </div>
        {text !== null ? (
          <>
            <label className="n-field">{t.mineChange}<textarea maxLength={2000} rows={4} value={text} onChange={(x) => setText(x.target.value)} /></label>
            <Button variant="primary" disabled={off || !text.trim()} onClick={() => void run("edited", () => reply(intentId, e.kpi_id, { action: "mine", wording: text })).then(() => setText(null))}>{t.save}</Button>
          </>
        ) : null}
        <label className="n-field">{t.notMine}
          <select aria-label={t.notMinePick} value={who} onChange={(x) => setWho(x.target.value)}>
            <option value="">{t.notMineIdk}</option>
            {people.map((n) => <option key={n} value={n}>{n}</option>)}
          </select>
        </label>
        <Button disabled={off} onClick={() => void run("not_mine", () => reply(intentId, e.kpi_id, { action: "not_mine", owner: who }))}>
          {who ? `${t.notMine} ${who}` : `Not mine, ${t.notMineIdk}`}
        </Button>
      </Panel>
      {q ? (
        <Panel title={q.question}>
          {q.suggestion ? <p><Pill tone="draft">{t.suggestion}</Pill> {q.suggestion.value}</p> : null}
          {q.suggestion ? (
            <Button disabled={off} onClick={() => void run("answer", () => answerAmbiguity(bid, e.kpi_id, q.id, q.suggestion?.value ?? ""))}>{t.useSuggestion}</Button>
          ) : null}
          <label className="n-field">{t.bothNote}<textarea maxLength={2000} rows={2} value={note} onChange={(x) => setNote(x.target.value)} /></label>
          <Button disabled={off} onClick={() => void run("both", () => reply(intentId, e.kpi_id, { action: "both_used", amb_id: q.id, note }))}>{t.bothUsed}</Button>
        </Panel>
      ) : null}
    </div>
  );
}

function Settle({ data, busy, run, intentId }: { data: Data; busy: string | null; run: Run; intentId: string }) {
  const { user } = useSession();
  const settler = data.start.can_settle ?? (user?.roles ?? []).some((r) => r === "company_admin" || r === "sponsor");
  const [pick, setPick] = useState<string | null>(null);
  const [reason, setReason] = useState("");
  const [tried, setTried] = useState(false);
  const [answer, setAnswer] = useState("");
  const [second, setSecond] = useState("");
  const [why, setWhy] = useState("");
  const bid = data.start.baseline_id ?? "";
  const terms = new Set((data.view?.entries ?? []).map((e) => e.kpi_id));
  const rows = data.ambs.filter((a) => terms.has(a.kpi_id) && !a.derived);
  const a = rows.find((x) => x.id === pick);
  if (data.closed) return <Panel><p>{t.closedForRole}</p></Panel>;
  if (!rows.length) return <Panel><p>{t.noAmbiguities}</p></Panel>;
  const off = busy !== null || data.view?.signed === true || !settler;
  return (
    <div className="ic-settle" style={{ display: "flex", flexWrap: "wrap", gap: 16 }}>
      {!a ? (
        <Panel title="Ambiguous terms" className="ic-settle-list">
          <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
            {rows.map((x) => (
              <li key={x.id} style={{ borderTop: "1px solid var(--line, #e5e5e5)", padding: "8px 0" }}>
                <button type="button" onClick={() => setPick(x.id)} style={{ background: "none", border: 0, padding: 0, textAlign: "left", cursor: "pointer" }}>
                  <strong>{x.kpi_name}</strong> <Pill tone={x.status === "open" ? "late" : "ok"}>{x.status === "accepted" ? "Accepted as risk" : x.status === "open" ? "Open" : "Settled"}</Pill>
                  <span style={{ display: "block" }}>{x.text}</span>
                  <span className="n-muted">{x.asked ? `Asked ${x.asked.owner}` : "Owner not asked yet"}{x.at ? `, raised ${x.at.slice(0, 10)}` : ""}</span>
                </button>
              </li>
            ))}
          </ul>
        </Panel>
      ) : (
        <Panel title={a.kpi_name} actions={<Button onClick={() => setPick(null)}>{t.back}</Button>}>
          <h3>{t.meanings}</h3>
          <table><tbody><tr><td>{a.text}</td><td className="n-muted">{a.where}</td></tr></tbody></table>
          <p>{a.question}</p>
          {a.suggestion ? <p><Pill tone="draft">{t.suggestion}</Pill> {a.suggestion.value}</p> : null}
          {a.status === "open" ? (
            <>
              <label className="n-field">{t.pickMeaning}<input value={answer} onChange={(x) => setAnswer(x.target.value)} placeholder={a.suggestion?.value ?? ""} /></label>
              <Button variant="primary" disabled={off || !(answer.trim() || a.suggestion?.value)}
                onClick={() => void run("pick", () => answerAmbiguity(bid, a.kpi_id, a.id, answer.trim() || a.suggestion?.value || ""))}>{t.pickMeaning}</Button>
              <label className="n-field">{t.secondName}<input value={second} onChange={(x) => setSecond(x.target.value)} /></label>
              <Button disabled={off || !second.trim()} onClick={() => void run("keep_both", () => reply(intentId, a.kpi_id, { action: "keep_both", amb_id: a.id, second_term: second.trim() }))}>{t.keepBoth}</Button>
              <label className="n-field">{t.reason}<textarea maxLength={2000} rows={3} value={reason} onChange={(x) => setReason(x.target.value)} /></label>
              {tried && !reason.trim() ? <p role="alert">{t.reasonRequired}</p> : null}
              <Button disabled={off} onClick={() => { setTried(true); if (reason.trim()) void run("accept", () => acceptAmbiguity(bid, a.kpi_id, a.id, reason.trim())); }}>{t.accept}</Button>
            </>
          ) : (
            <>
              <p>{a.status === "accepted" ? `Accepted by ${a.by ?? ""}: ${a.resolution ?? ""}` : `Settled by ${a.by ?? ""}: ${a.resolution ?? ""}`}</p>
              <label className="n-field">{t.reopenWhy}<textarea maxLength={2000} rows={2} value={why} onChange={(x) => setWhy(x.target.value)} /></label>
              <Button disabled={off || !why.trim()} onClick={() => void run("reopen", () => reply(intentId, a.kpi_id, { action: "reopen", amb_id: a.id, reason: why.trim() }))}>{t.reopen}</Button>
            </>
          )}
        </Panel>
      )}
    </div>
  );
}
