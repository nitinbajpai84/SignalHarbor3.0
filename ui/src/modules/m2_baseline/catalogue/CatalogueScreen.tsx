import { useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";

import { ApiError } from "../../../api/client";
import DownloadButton from "../../../components/DownloadButton";
import PageHead from "../../../components/PageHead";
import Panel from "../../../components/Panel";
import ScreenState from "../../../components/ScreenState";
import { useLoad } from "../../../components/useLoad";
import { CAT_TABS, catalogueExportUrl, cellOf, cellText, getCatalogue, refreshCatalogue, type CatTab, type CatalogueView, type Conflict } from "../api";
import BaselineSteps from "../BaselineSteps";
import { m2Cat as t } from "../copy";
import CatalogueTab, { hasUnknown } from "./CatalogueTab";
import ConflictPanel from "./ConflictPanel";
import GovernanceColumns from "../governance/GovernanceColumns";
import TechnicalColumns from "../technical/TechnicalColumns";

const isEmpty = (c: CatalogueView) => CAT_TABS.every((tab) => c[tab].length === 0) && c.conflicts.length === 0;

/** M2-20: the catalogue's five tabs as screens. Stated, guessed and unknown on every row; a filter for the unknowns; the spreadsheet to download. */
export default function CatalogueScreen() {
  const { baselineId = "" } = useParams();
  const cat = useLoad(() => getCatalogue(baselineId), `m2-catalogue-${baselineId}`, isEmpty);
  const [params] = useSearchParams();
  const asked = params.get("tab");
  const [tab, setTab] = useState<CatTab>(CAT_TABS.find((k) => k === asked) ?? "sources"); // M2-E1: a link from a technical definition opens the tab of the row
  const [onlyUnknown, setOnlyUnknown] = useState(false);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = async () => {
    setBusy(true);
    setError(null);
    setNote(null);
    try {
      await refreshCatalogue(baselineId);
      setNote(t.refreshed);
      cat.retry();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "That could not be done. Please try again.");
    } finally {
      setBusy(false);
    }
  };

  const actions = (
    <>
      <button type="button" className="n-btn" disabled={busy} onClick={() => void refresh()}>
        {busy ? t.refreshing : t.refresh}
      </button>
      <DownloadButton primary path={catalogueExportUrl(baselineId)} fallbackName="data-catalogue.xlsx" label={t.download} />
    </>
  );

  return (
    <>
      <PageHead eyebrow={t.eyebrow} title={t.title} sub={t.sub} actions={actions} />
      <BaselineSteps baselineId={baselineId} signed={cat.data?.signed === true} />
      {note ? <p role="status">{note}</p> : null}
      {error ? (
        <p role="alert" className="state state-error">
          {error}
        </p>
      ) : null}
      <ScreenState state={cat.state} message={cat.state === "empty" ? t.empty : cat.message} onRetry={cat.retry}>
        {cat.data ? <Loaded cat={cat.data} tab={tab} setTab={setTab} onlyUnknown={onlyUnknown} setOnlyUnknown={setOnlyUnknown} baselineId={baselineId} onChanged={cat.retry} /> : null}
      </ScreenState>
    </>
  );
}

interface LoadedProps {
  cat: CatalogueView;
  tab: CatTab;
  setTab: (t: CatTab) => void;
  onlyUnknown: boolean;
  setOnlyUnknown: (v: boolean) => void;
  baselineId: string;
  onChanged: () => void;
}

function Loaded({ cat, tab, setTab, onlyUnknown, setOnlyUnknown, baselineId, onChanged }: LoadedProps) {
  const ids = Object.fromEntries(CAT_TABS.map((k) => [k, cat[k].map((r) => cellText(cellOf(r, cat.schema[k].id_header)))])) as Record<CatTab, string[]>;
  const sourceName = (c: Conflict) => {
    const row = cat.sources.find((r) => cellText(cellOf(r, cat.schema.sources.id_header)) === c.row_id);
    return (row && cellText(cellOf(row, "Source name"))) || c.row_id || "";
  };
  const unknowns = (k: CatTab) => cat[k].filter((r) => hasUnknown(r, cat.schema[k], k)).length;
  return (
    <>
      {cat.hidden_note ? <p role="status">{cat.hidden_note}</p> : null}
      <fieldset disabled={cat.signed === true} style={{ border: 0, padding: 0, margin: 0, minWidth: 0 }}>
        <ConflictPanel baselineId={baselineId} conflicts={cat.conflicts} rowName={sourceName} onChanged={onChanged} />
      </fieldset>
      <Panel>
        <div role="tablist" aria-label={t.tabsLabel} className="n-tabs">
          {CAT_TABS.map((k) => (
            <button key={k} type="button" role="tab" id={`m2-tab-${k}`} aria-selected={tab === k} aria-controls="m2-tabpanel" className={`n-tab${tab === k ? " active" : ""}`} onClick={() => setTab(k)}>
              {t.tabs[k]} ({cat[k].length})
            </button>
          ))}
        </div>
        <label className="m1-choice">
          <input type="checkbox" checked={onlyUnknown} onChange={(e) => setOnlyUnknown(e.target.checked)} />
          {t.filterUnknown} ({unknowns(tab)})
        </label>
        <div role="tabpanel" id="m2-tabpanel" aria-labelledby={`m2-tab-${tab}`}>
          <fieldset disabled={cat.signed === true} style={{ border: 0, padding: 0, margin: 0, minWidth: 0 }}>
            <CatalogueTab key={tab} baselineId={baselineId} tab={tab} schema={cat.schema[tab]} rows={cat[tab]} ids={ids} findings={cat.findings} onlyUnknown={onlyUnknown} onChanged={onChanged} />
          </fieldset>
          <GovernanceColumns tab={tab} schema={cat.schema[tab]} rows={cat[tab]} governance={cat.governance} />
          <TechnicalColumns tab={tab} schema={cat.schema[tab]} rows={cat[tab]} technical={cat.technical} />
        </div>
      </Panel>
    </>
  );
}
