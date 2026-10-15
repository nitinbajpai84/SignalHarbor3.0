import { useEffect, useState } from "react";

import ScreenState from "../../components/ScreenState";
import { useLoad } from "../../components/useLoad";
import { DataTable, PageFrame, Pill, StatCard, StatGrid } from "../../design";
import BuildNav from "../b6/BuildNav";
import DeliveriesSection from "../k10/DeliveriesSection";
import { getHealth, getPipelines, type PipelineRow } from "./api";
import { day } from "./dates";
import RunsSection from "./RunsSection";
import SourcesTable from "./SourcesTable";

// Operations: is everything arriving and running? The old Map Health tab, now under Build. Data team only (the server refuses everyone else, same as before).
// Sections are plain blocks inside the frame: Sources, Live pipelines, Deliveries (the Morning Note by email and in Slack, moved here from Consume).
const state = (p: PipelineRow) => !p.last_run ? <span className="ds-muted">Not run yet</span>
  : p.last_run.status === "ok" ? <Pill tone="ok">Healthy</Pill> : <Pill tone="late">{p.last_run.status === "late" ? "Ran late" : "Failed"}</Pill>;
const checks = (p: PipelineRow) => (p.last_run ? `${p.last_run.rules.filter((r) => r.passed).length} of ${p.last_run.rules.length}` : "Not run yet");
const time = (iso: string) => new Date(iso).toLocaleString("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });

export default function OperationsPage() {
  const health = useLoad(getHealth, "k3-health", (h) => h.allowed && h.sources.length === 0);
  const [pipes, setPipes] = useState<PipelineRow[] | null>(null);
  useEffect(() => { void getPipelines().then((r) => setPipes(r.pipelines), () => setPipes([])); }, []);
  const h = health.data;
  const refused = h !== null && !h.allowed;
  const sources = h?.sources ?? [];
  const onTime = sources.filter((s) => !s.is_late && !s.never_received).length;
  const stale = sources.some((s) => s.stale !== null) ? sources.reduce((a, s) => a + (s.stale ?? 0), 0) : null;
  const ran = (pipes ?? []).filter((p) => p.last_run?.status === "ok").length;
  return (
    <PageFrame title="Operations: is everything arriving and running?"
      subline="For the data team. Each source and each live pipeline, today. Anything wrong also lands in Action for the person who owns it.">
      <BuildNav current="operations" />
      <ScreenState state={refused ? "refused" : health.state} message={refused ? "Source health is for the data team." : health.state === "empty" ? "No source has been set up yet." : health.message} onRetry={health.retry}>
        {h ? (
          <div style={{ display: "grid", gap: 16 }}>
            <StatGrid cols={4}>
              <StatCard label="Sources on time" value={`${onTime} of ${sources.length}`} />
              <StatCard label="Pipelines whose last run was healthy" value={pipes ? `${ran} of ${pipes.length}` : "Not available yet"} />
              <StatCard label="Files turned away" value={h.totals.rejected ?? 0} valueTone={h.totals.rejected ? "warn" : undefined} />
              <StatCard label="Values older than 90 days" value={stale ?? "Not available yet"} />
            </StatGrid>
            <section aria-label="Sources"><h2 style={{ fontSize: 17 }}>Sources</h2><SourcesTable sources={sources} /></section>
            <section aria-label="Pipelines"><h2 style={{ fontSize: 17 }}>Live pipelines</h2>
              {pipes && pipes.length ? (
                <DataTable columns={[{ key: "p", label: "Pipeline" }, { key: "last", label: "Last run" }, { key: "took", label: "Took" }, { key: "checks", label: "Checks" }, { key: "state", label: "State" }, { key: "next", label: "Next run" }]}
                  rows={pipes.map((p) => ({ p: <><strong>{p.title}</strong><div className="ds-footnote">Owner {p.owner ?? "not named yet"}</div></>,
                    last: p.last_run ? time(p.last_run.started) : day(null), took: p.last_run?.seconds != null ? `${p.last_run.seconds} s` : "Not available yet", checks: checks(p), state: state(p),
                    next: p.next_run ? time(p.next_run) : "Not scheduled" }))} />
              ) : <p className="ds-muted">{pipes ? "No pipeline is live yet." : "Reading the pipelines."}</p>}
            </section>
            <RunsSection />
            <DeliveriesSection />
          </div>
        ) : null}
      </ScreenState>
    </PageFrame>
  );
}
