import { useState } from "react";
import { useParams } from "react-router-dom";

import { ApiError } from "../../../api/client";
import PageHead from "../../../components/PageHead";
import Panel from "../../../components/Panel";
import ScreenState from "../../../components/ScreenState";
import StatusPill from "../../../components/StatusPill";
import { useLoad } from "../../m1_intent/useLoad";
import { confirmProposals, getGovernance, restrictField, type GovCount, type GovRow, type GovernanceView } from "../api";
import BaselineSteps from "../BaselineSteps";
import { m2Gov as t } from "../copy";

const isEmpty = (g: GovernanceView) => g.measures.length === 0 && g.other_sources.length === 0 && g.other_fields.length === 0;

/** What the row says about personal data in plain words: yes, no, or not decided. */
export function holds(r: GovRow): string {
  const p = (r.personal ?? "").toLowerCase();
  if (r.kind === "measure") return p === "yes" ? t.yes : p === "no" ? t.no : t.notDecided;
  return p === "" || p === "not sure" ? t.notDecided : r.personal ?? t.notDecided;
}
const isPersonal = (r: GovRow) => ["yes", "personal data", "sensitive to the business"].includes((r.personal ?? "").toLowerCase());
const yesNo = (v: boolean | null | undefined) => (v === null || v === undefined ? "" : v ? t.yes : t.no);

interface Line {
  row: GovRow;
  parent: string;
}
function lines(g: GovernanceView): Line[] {
  const out: Line[] = [];
  for (const m of g.measures) {
    out.push({ row: m, parent: "" });
    for (const r of [...(m.sources ?? []), ...(m.fields ?? [])]) out.push({ row: r, parent: m.name });
  }
  for (const r of [...g.other_sources, ...g.other_fields]) out.push({ row: r, parent: "" });
  return out;
}

function Counts({ label, c }: { label: string; c: GovCount }) {
  return (
    <p>
      <strong>{label}:</strong> {c.total} · {c.decided} {t.decided} · {c.undecided} {t.undecided} · {c.restricted} {t.restricted}
    </p>
  );
}

/** M2-E3: the governance of the whole baseline in one table: personal data, sensitive, who may see it, who decided and what is left. */
export default function GovernanceScreen() {
  const { baselineId = "" } = useParams();
  const gov = useLoad(() => getGovernance(baselineId), `m2-governance-${baselineId}`, isEmpty);
  const [filters, setFilters] = useState({ undecided: false, personal: false, restricted: false });
  const [note, setNote] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const act = async (p: Promise<unknown>, done: string | ((r: never) => string)) => {
    setError(null);
    setNote(null);
    try {
      const r = await p;
      setNote(typeof done === "string" ? done : done(r as never));
      gov.retry();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "That could not be saved. Please try again.");
    }
  };
  const signed = gov.data?.signed === true;
  const hasProposals = lines(gov.data ?? ({ measures: [], other_sources: [], other_fields: [] } as unknown as GovernanceView)).some((l) => l.row.proposal?.class === "Neither");
  const confirmAll = (
    <button type="button" className="n-btn" disabled={signed || !hasProposals} onClick={() => void act(confirmProposals(baselineId, { only_not_personal: true }), (r: { confirmed: string[] }) => t.confirmed(r.confirmed.length))}>
      {t.confirmAll}
    </button>
  );

  return (
    <>
      <PageHead eyebrow={t.eyebrow} title={t.title} sub={t.sub} actions={confirmAll} />
      <BaselineSteps baselineId={baselineId} signed={signed} />
      {note ? <p role="status">{note}</p> : null}
      {error ? (
        <p role="alert" className="state state-error">
          {error}
        </p>
      ) : null}
      <ScreenState state={gov.state} message={gov.state === "empty" ? t.empty : gov.message} onRetry={gov.retry}>
        {gov.data ? <Loaded g={gov.data} filters={filters} setFilters={setFilters} baselineId={baselineId} act={act} /> : null}
      </ScreenState>
    </>
  );
}

type Act = (p: Promise<unknown>, done: string | ((r: never) => string)) => Promise<void>;
interface LoadedProps {
  g: GovernanceView;
  filters: { undecided: boolean; personal: boolean; restricted: boolean };
  setFilters: (f: LoadedProps["filters"]) => void;
  baselineId: string;
  act: Act;
}

function Loaded({ g, filters, setFilters, baselineId, act }: LoadedProps) {
  const all = lines(g);
  const keep = (r: GovRow) => !r.hidden && (!filters.undecided || (r.undecided ?? []).length > 0) && (!filters.personal || isPersonal(r)) && (!filters.restricted || r.restricted);
  const anyFilter = filters.undecided || filters.personal || filters.restricted;
  const shown = anyFilter ? all.filter((l) => keep(l.row)) : all;
  const s = g.summary;
  return (
    <>
      {g.organiser ? <p className="n-muted">{t.organiserNote}</p> : null}
      {g.note ? <p role="note">{g.note}</p> : null}
      <Panel title={t.summaryTitle}>
        <Counts label={t.measures} c={s.measures} />
        <Counts label={t.sources} c={s.sources} />
        <Counts label={t.fields} c={s.fields} />
        {s.lines.length ? (
          <ul>
            {s.lines.map((l) => (
              <li key={l}>{l}</li>
            ))}
          </ul>
        ) : (
          <p className="n-muted">{t.allDecided}</p>
        )}
      </Panel>
      <Panel>
        <fieldset className="n-flex wrap" style={{ border: 0, padding: 0, margin: 0 }}>
          <legend>{t.filtersLabel}</legend>
          {(
            [
              ["undecided", t.filterUndecided],
              ["personal", t.filterPersonal],
              ["restricted", t.filterRestricted],
            ] as const
          ).map(([k, label]) => (
            <label key={k} className="m1-choice">
              <input type="checkbox" checked={filters[k]} onChange={(e) => setFilters({ ...filters, [k]: e.target.checked })} /> {label}
            </label>
          ))}
        </fieldset>
        {!g.can_change ? <p className="n-muted">{t.readOnlyNote}</p> : null}
        {shown.length === 0 ? (
          <p className="n-muted">{t.nothingShown}</p>
        ) : (
          <fieldset disabled={g.signed} style={{ border: 0, padding: 0, margin: 0, minWidth: 0 }}>
            <table className="n-table" aria-label={t.tableLabel}>
              <thead>
                <tr>
                  <th>{t.cols.name}</th>
                  <th>{t.cols.personal}</th>
                  <th>{t.cols.sensitive}</th>
                  <th>{t.cols.who}</th>
                  <th>{t.cols.decided}</th>
                  <th>{t.cols.left}</th>
                </tr>
              </thead>
              <tbody>
                {shown.map((l) => (
                  <GovLine key={`${l.row.kind}-${l.parent}-${l.row.id}`} line={l} baselineId={baselineId} canChange={g.can_change} act={act} />
                ))}
              </tbody>
            </table>
          </fieldset>
        )}
      </Panel>
    </>
  );
}

function GovLine({ line, baselineId, canChange, act }: { line: Line; baselineId: string; canChange: boolean; act: Act }) {
  const r = line.row;
  const [editing, setEditing] = useState(false);
  const [names, setNames] = useState((r.visible_to?.mode === "named" ? r.visible_to.names : []).join(", "));
  const left = r.undecided ?? [];
  const save = async () => {
    await act(restrictField(baselineId, r.id, names.split(",").map((n) => n.trim()).filter(Boolean)), t.limited);
    setEditing(false);
  };
  return (
    <tr>
      <td style={{ paddingLeft: line.parent ? 24 : undefined }}>
        <strong>{r.name}</strong> <span className="n-muted">{t.kinds[r.kind]}{line.parent ? ` · ${line.parent}` : ""}</span>
      </td>
      <td>
        {holds(r)}
        {r.proposal ? (
          <div>
            <StatusPill tone="warning">{t.suggestion}</StatusPill> {t.suggests(r.proposal.class)}
            <div className="n-muted">{r.proposal.reason}</div>
            <button type="button" className="n-btn sm" onClick={() => void act(confirmProposals(baselineId, { field_ids: [r.id] }), (x: { confirmed: string[] }) => t.confirmed(x.confirmed.length))}>
              {t.confirm}
            </button>
          </div>
        ) : null}
      </td>
      <td>{yesNo(r.sensitive)}</td>
      <td>
        {r.visible_to?.text}
        {r.kind === "field" && canChange ? (
          editing ? (
            <div>
              <label>
                {t.limit}
                <input className="n-input" value={names} onChange={(e) => setNames(e.target.value)} />
              </label>
              <p className="n-muted">{t.limitHelp}</p>
              <button type="button" className="n-btn sm" onClick={() => void save()}>
                {t.limitSave}
              </button>{" "}
              <button type="button" className="n-btn sm" onClick={() => setEditing(false)}>
                {t.limitCancel}
              </button>
            </div>
          ) : (
            <div>
              <button type="button" className="n-btn sm" onClick={() => setEditing(true)}>
                {t.limit}
              </button>
            </div>
          )
        ) : null}
      </td>
      <td>{r.decided ? t.by(r.decided.by, r.decided.at) : left.length ? "" : t.notRecorded}</td>
      <td>{left.join("; ")}</td>
    </tr>
  );
}
