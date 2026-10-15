import { useState } from "react";

import { ApiError, apiGet, apiSend } from "../../api/client";
import Panel from "../../components/Panel";
import ScreenState from "../../components/ScreenState";
import { useLoad } from "../../components/useLoad";
import { Button, Pill } from "../../design";
import type { MapSource, ZoneId } from "../../modules/m3_connect/api";
import { truthText } from "../../modules/m3_connect/truth/copy";
import SourceQuadrant from "../../modules/m3_connect/truth/SourceQuadrant";
import { smCopy as t } from "./SourceMapTabCopy";

// B37: the source map of an Intent, in Define (?tab=source-map). The plot is the Moment of truth's own quadrant (read only here); the position
// and the Lens draft come from the server, a person's confirmation carries a reason. Every figure shows the records it was counted from.

interface Check { key: string; ok: boolean; trace: string }
interface Classification { strategic: boolean; reason: string; mark: "guessed" | "stated"; by: string; at: string | null; moved_since: boolean }
interface MapRow {
  id: string;
  name: string;
  restricted: boolean;
  silhouette: boolean;
  zone?: ZoneId;
  impact?: { count: number; must: number; should: number; score: number; measures: { id: string; name: string; priority: string }[] };
  readiness?: { count: number; of: number; score: number; checks: Check[] };
  classification?: Classification;
}
interface MapData {
  available: boolean;
  missing?: string;
  sources: MapRow[];
  left_out?: number;
  restricted?: number;
  written?: boolean;
  can_confirm?: boolean;
  thresholds?: { full: number; high_from: number; ready_from: number };
}

const URL = (id: string) => `/api/intents/sources/map?intent_id=${encodeURIComponent(id)}`;
const day = (iso: string | null) => (iso ? new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" }) : "");
const asPoint = (r: MapRow): MapSource => ({
  id: r.id, name: r.name, restricted: r.silhouette, kind: "hidden", measures_fed: r.impact?.count ?? 0, impact: r.impact?.score ?? 0,
  readiness: r.readiness?.score ?? 0, zone: r.zone ?? "identify", zone_label: "", marks: {}, summary: "", override: null,
});

function Confirm({ row, intentId, onSaved }: { row: MapRow; intentId: string; onSaved: (d: MapData) => void }) {
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState("");
  async function send(strategic: boolean) {
    if (reason.trim().length < 5) return setProblem(t.needReason);
    setBusy(true);
    setProblem("");
    try {
      onSaved(await apiSend<MapData>("POST", URL(intentId), { source_id: row.id, strategic, reason: reason.trim() }));
      setReason("");
    } catch (e) {
      setProblem(e instanceof ApiError && e.status !== 0 && e.status < 500 ? e.message : t.failed);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div role="group" aria-label={`${t.why} ${row.name}`} style={{ display: "grid", gap: 8, marginTop: 8 }}>
      <label>
        {t.reasonLabel}
        <input value={reason} maxLength={300} onChange={(e) => setReason(e.target.value)} style={{ width: "100%" }} />
      </label>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <Button variant="primary" disabled={busy} onClick={() => void send(true)}>{busy ? t.saving : t.confirmStrategic}</Button>
        <Button disabled={busy} onClick={() => void send(false)}>{t.confirmNot}</Button>
      </div>
      {problem ? <p role="alert" className="ds-warn">{problem}</p> : null}
    </div>
  );
}

function Card({ row, intentId, canConfirm, onSaved }: { row: MapRow; intentId: string; canConfirm: boolean; onSaved: (d: MapData) => void }) {
  if (row.silhouette) {
    return (
      <li className="ds-card" style={{ padding: 12, listStyle: "none", borderStyle: "dashed" }}>
        <strong>{t.restricted}</strong>
        <p className="n-muted">{t.restrictedNote}</p>
      </li>
    );
  }
  const im = row.impact!, rd = row.readiness!, cl = row.classification!;
  return (
    <li className="ds-card" style={{ padding: 12, listStyle: "none", display: "grid", gap: 6 }} data-source={row.id}>
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <strong>{row.name}</strong>
        <Pill tone={row.zone === "p1" ? "ok" : row.zone === "unknown" ? "late" : "draft"}>{truthText.zones[row.zone!]}</Pill>
        {row.restricted ? <Pill tone="restricted">{t.restricted}</Pill> : null}
      </div>
      <p style={{ margin: 0 }}>
        {t.axes.impact}: {im.count ? t.feeds(im.must, im.should) : t.feedsNone}
        {im.measures.length ? <span className="n-muted">{` (${im.measures.map((m) => m.name).join(", ")})`}</span> : null}
      </p>
      <p style={{ margin: 0 }}>{t.axes.readiness}: {rd.count} of {rd.of}</p>
      <ul aria-label={t.checkTitle} style={{ margin: 0, paddingLeft: 18 }}>
        {rd.checks.map((c) => (
          <li key={c.key}>{t.checks[c.key]}: {c.ok ? t.pass : t.fail} <span className="n-muted">({c.trace})</span></li>
        ))}
      </ul>
      <p style={{ margin: 0 }}>
        <strong>{cl.strategic ? t.strategic : t.notStrategic}</strong>
        {" · "}
        {cl.mark === "stated" ? t.confirmedBy(cl.by, day(cl.at)) : t.guess(cl.by)}
      </p>
      <p className="n-muted" style={{ margin: 0 }}>{cl.reason}</p>
      {cl.moved_since ? <p role="status" className="ds-warn">{t.moved}</p> : null}
      {canConfirm ? <Confirm row={row} intentId={intentId} onSaved={onSaved} /> : null}
    </li>
  );
}

export function SourceMapTab({ intentId }: { intentId: string }) {
  const load = useLoad<MapData>(() => apiGet<MapData>(URL(intentId)), intentId);
  const [fresh, setFresh] = useState<MapData | null>(null);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState("");
  const d = fresh ?? load.data;
  async function ask() {
    setBusy(true);
    setProblem("");
    try {
      setFresh(await apiSend<MapData>("POST", URL(intentId), {}));
    } catch (e) {
      setProblem(e instanceof ApiError && e.status !== 0 && e.status < 500 ? e.message : t.failed);
    } finally {
      setBusy(false);
    }
  }
  const rows = d?.sources ?? [];
  const state = load.state === "populated" && d && (!d.available || rows.length === 0) ? "empty" : load.state;
  const confirmed = rows.filter((r) => r.classification?.mark === "stated").length;
  return (
    <Panel
      title={t.title}
      actions={d?.available && d.can_confirm ? <Button variant="primary" disabled={busy} onClick={() => void ask()}>{busy ? t.drafting : t.draft}</Button> : undefined}
    >
      <ScreenState state={state} message={state === "empty" ? (d && !d.available ? t.noBaseline : t.empty) : load.message} onRetry={load.retry}>
        {d ? (
          <div style={{ display: "grid", gap: 12, minWidth: 0 }}>
            <p className="n-muted">{t.lede}</p>
            {d.thresholds ? <p className="n-muted">{t.rule(d.thresholds.high_from, d.thresholds.ready_from, d.thresholds.full)}</p> : null}
            <p role="status">{t.counts(rows.filter((r) => !r.silhouette).length, confirmed, d.restricted ?? 0, d.left_out ?? 0)}</p>
            {d.written ? null : <p className="n-muted">{t.notWritten}</p>}
            {problem ? <p role="alert" className="ds-warn">{problem}</p> : null}
            <div style={{ overflowX: "auto", maxWidth: "100%", minWidth: 0 }}>
              <SourceQuadrant sources={rows.filter((r) => !r.silhouette).map(asPoint)} canMove={false} onMove={async () => undefined} />
            </div>
            {d.restricted ? <p className="n-muted">{t.restrictedLine(d.restricted)}</p> : null}
            <h3>{t.listTitle}</h3>
            <ul style={{ display: "grid", gap: 8, padding: 0, margin: 0 }}>
              {rows.map((r) => <Card key={r.id} row={r} intentId={intentId} canConfirm={!!d.can_confirm} onSaved={setFresh} />)}
            </ul>
          </div>
        ) : null}
      </ScreenState>
    </Panel>
  );
}

export default SourceMapTab;
