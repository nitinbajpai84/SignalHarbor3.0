import { useState } from "react";

import StatusPill, { type PillTone } from "../../../components/StatusPill";
import { ApiError } from "../../../api/client";
import { addCatalogueRow, cellOf, cellText, editCatalogueRow, type CatCell, type CatColumn, type CatRow, type CatTab, type CatTabSchema, type Mark } from "../api";
import { m2Cat as t } from "../copy";

interface Props {
  baselineId: string;
  tab: CatTab;
  schema: CatTabSchema;
  rows: CatRow[];
  /** The ids on the other tabs, for the columns that pick one ("From tab 1", "Feeds KPI"). */
  ids: Record<CatTab, string[]>;
  findings: Record<string, string[]>;
  onlyUnknown: boolean;
  onChanged: () => void;
}

const TONE: Record<Mark, PillTone> = { stated: "success", guessed: "warning", unknown: "muted" };

/** A cell with its chip: stated, guessed or unknown. An unknown required cell says so; it is never left looking filled. */
export function CellView({ cell, required, missing }: { cell: CatCell | undefined; required: boolean; missing?: string }) {
  const text = cellText(cell);
  if (!text) return required ? <StatusPill tone="muted">{missing ?? t.unknown}</StatusPill> : <span className="n-muted">Not set</span>;
  const title = cell ? t.said(cell.by, cell.at, cell.from) : "";
  return cell?.mark === "guessed" ? (
    <span title={title}>
      {text} <StatusPill tone="warning">{t.marks.guessed}</StatusPill>
    </span>
  ) : (
    <span title={title}>{text}</span>
  );
}

/** A field with no known meaning says so in words, rather than a bare "Unknown". */
const missingWords = (tab: CatTab, header: string) => (tab === "fields" && header === "Business meaning" ? t.notAvailable : undefined);

function rowId(row: CatRow, schema: CatTabSchema): string {
  return cellText(cellOf(row, schema.id_header));
}

/** Something is unknown: a required cell with no answer, or the row is not complete or ready. */
export function hasUnknown(row: CatRow, schema: CatTabSchema, tab?: CatTab): boolean {
  if (row._hidden) return false;
  const status = cellText(cellOf(row, schema.status_header));
  const shown = new Set(tab ? t.listColumns[tab] ?? [] : []);
  // a required cell the list shows as "Unknown" counts, computed or not: the count must match what the person sees
  const blank = (c: CatColumn) => c.required && (!c.computed || shown.has(c.header)) && !cellText(cellOf(row, c.header));
  return schema.columns.some(blank) || !["Complete", "Ready"].includes(status);
}

export default function CatalogueTab({ baselineId, tab, schema, rows, ids, findings, onlyUnknown, onChanged }: Props) {
  const [open, setOpen] = useState<string | null>(null);
  const [form, setForm] = useState<{ id: string | null; cells: Record<string, string>; original: Record<string, string>; guess: boolean } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const byHeader = new Map(schema.columns.map((c) => [c.header, c]));
  const shownCols = (t.listColumns[tab] ?? []).map((h) => byHeader.get(h)).filter((c): c is CatColumn => !!c);
  const sure = byHeader.get(t.sureHeader);
  const shownRows = onlyUnknown ? rows.filter((r) => hasUnknown(r, schema, tab)) : rows;

  const startAdd = () => setForm({ id: null, cells: {}, original: {}, guess: false });
  const startEdit = (row: CatRow) => {
    const cells: Record<string, string> = {};
    schema.columns.filter((c) => !c.computed && c.header !== schema.id_header).forEach((c) => (cells[c.header] = cellText(cellOf(row, c.header))));
    setForm({ id: rowId(row, schema), cells, original: cells, guess: false });
  };

  const save = async () => {
    if (!form) return;
    setBusy(true);
    setError(null);
    try {
      const mark: Mark = form.guess ? "guessed" : "stated";
      // Only what the person changed is sent, so the cells they did not touch keep who said them.
      const changed = Object.entries(form.cells).filter(([h, v]) => (form.id ? v !== (form.original[h] ?? "") : v.trim()));
      const cells = Object.fromEntries(changed);
      if (form.id && changed.length === 0) {
        setForm(null);
        return;
      }
      if (form.id) await editCatalogueRow(baselineId, tab, form.id, cells, mark);
      else await addCatalogueRow(baselineId, tab, cells, mark);
      setForm(null);
      onChanged();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "That could not be saved. Please try again.");
    } finally {
      setBusy(false);
    }
  };

  const input = (c: CatColumn) => {
    const value = form?.cells[c.header] ?? "";
    const set = (v: string) => setForm((f) => (f ? { ...f, cells: { ...f.cells, [c.header]: v } } : f));
    const choices = c.options.length ? c.options : c.picks_from ? ids[c.picks_from] : [];
    const several = (tab === "tables" && c.header === "Related KPIs") || c.header === "Feeds KPI"; // these hold every KPI, written "K01, K02"
    return choices.length && !several ? (
      <select value={value} onChange={(e) => set(e.target.value)}>
        <option value="">{t.pick}</option>
        {choices.map((o) => (
          <option key={o} value={o}>
            {o}
          </option>
        ))}
      </select>
    ) : (
      <input value={value} onChange={(e) => set(e.target.value)} />
    );
  };

  return (
    <div>
      <p className="n-muted">{t.intro[tab]}</p>
      {tab === "kpis" ? null : (
        <p>
          <button type="button" className="n-btn" onClick={startAdd}>
            {t.addTo(t.tabs[tab])}
          </button>
        </p>
      )}
      {form ? (
        <form
          className="m1-fieldset"
          aria-label={form.id ? `${t.edit} ${form.id}` : t.addTo(t.tabs[tab])}
          onSubmit={(e) => {
            e.preventDefault();
            void save();
          }}
        >
          {error ? (
            <p role="alert" className="state state-error">
              {error}
            </p>
          ) : null}
          {schema.columns
            .filter((c) => !c.computed && c.header !== schema.id_header)
            .map((c) => (
              <label key={c.header}>
                {c.header}
                {c.required ? " *" : ""}
                <span className="m1-help">{c.guidance === "Pick one" ? "" : c.guidance}</span>
                {input(c)}
              </label>
            ))}
          <label className="m1-choice">
            <input type="checkbox" checked={form.guess} onChange={(e) => setForm({ ...form, guess: e.target.checked })} />
            {t.fieldGuess}
          </label>
          <div className="m1-actions">
            <button type="submit" className="n-btn primary" disabled={busy}>
              {busy ? t.saving : t.save}
            </button>
            <button type="button" className="n-btn" onClick={() => setForm(null)}>
              {t.cancel}
            </button>
          </div>
        </form>
      ) : null}
      {rows.length === 0 ? (
        <p className="n-muted">{t.noRows}</p>
      ) : shownRows.length === 0 ? (
        <p className="n-muted">{t.nothingShown}</p>
      ) : (
        <div className="n-table-wrap">
          <table className="n-table">
            <caption className="n-muted">{schema.sheet}</caption>
            <thead>
              <tr>
                <th scope="col">{schema.id_header}</th>
                {shownCols.map((c) => (
                  <th key={c.header} scope="col">
                    {c.header}
                  </th>
                ))}
                {tab === "kpis" ? <th scope="col">{t.findingsHead}</th> : null}
                <th scope="col">{schema.status_header}</th>
                {sure ? <th scope="col">{sure.header}</th> : null}
                <th scope="col" />
              </tr>
            </thead>
            <tbody>
              {shownRows.map((row) => {
                const id = rowId(row, schema);
                if (row._hidden)
                  return (
                    <tr key={id}>
                      <td>{id}</td>
                      <td colSpan={shownCols.length + (tab === "kpis" ? 4 : 3)} className="n-muted">
                        {t.restricted}
                      </td>
                    </tr>
                  );
                const status = cellText(cellOf(row, schema.status_header));
                const mark = cellText(cellOf(row, t.sureHeader));
                return (
                  <tr key={id}>
                    <td>
                      {id}
                      {row._undecided ? (
                        <div>
                          <StatusPill tone="warning">{t.undecided}</StatusPill>
                        </div>
                      ) : null}
                    </td>
                    {shownCols.map((c) => (
                      <td key={c.header}>
                        <CellView cell={cellOf(row, c.header)} required={c.required || c.computed} missing={missingWords(tab, c.header)} />
                      </td>
                    ))}
                    {tab === "kpis" ? (
                      <td>
                        {(findings[id] ?? []).map((f) => (
                          <div key={f}>
                            <StatusPill tone={f === "nothing_mapped" ? "danger" : "warning"}>{t.findings[f] ?? f}</StatusPill>
                          </div>
                        ))}
                      </td>
                    ) : null}
                    <td>
                      <StatusPill tone={status === "Complete" || status === "Ready" ? "success" : "warning"}>{status}</StatusPill>
                    </td>
                    {sure ? (
                      <td>
                        <StatusPill tone={TONE[mark === "Guessed" ? "guessed" : mark.startsWith("Stated") ? "stated" : "unknown"]}>{t.howSure[mark] ?? t.marks.unknown}</StatusPill>
                      </td>
                    ) : null}
                    <td>
                      <button type="button" className="n-btn sm" aria-expanded={open === id} onClick={() => setOpen(open === id ? null : id)}>
                        {open === id ? t.close : t.open}
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      {open
        ? shownRows
            .filter((r) => !r._hidden && rowId(r, schema) === open)
            .map((row) => (
              <section key={open} aria-label={open} className="n-panel-body">
                <div className="m1-row">
                  <h3>{open}</h3>
                  <button type="button" className="n-btn sm" onClick={() => startEdit(row)}>
                    {t.edit}
                  </button>
                </div>
                <dl className="m1-review">
                  {schema.columns.map((c) => {
                    const cell = cellOf(row, c.header);
                    return (
                      <div key={c.header} style={{ display: "contents" }}>
                        <dt>{c.header}</dt>
                        <dd>
                          <CellView cell={cell} required={c.required || c.computed} missing={missingWords(tab, c.header)} />
                          {cell && cell.mark !== "unknown" && !c.computed ? <span className="n-muted"> · {t.said(cell.by, cell.at, cell.from)}</span> : null}
                        </dd>
                      </div>
                    );
                  })}
                </dl>
              </section>
            ))
        : null}
    </div>
  );
}
