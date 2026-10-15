import ChainPanel from "./build/ChainPanel";
import { useCallback, useEffect, useState, type ReactNode } from "react";

import { apiGet, Refused } from "../api/client";
import { copy } from "../copy";
import { Button, Chip, EmptyState, Footnote, PageFrame, RoomTile, SideCard } from "../design";
import { brCopy } from "../intents/views/buildReadyCopy";
import { DOORS_GRID } from "./CentrePage";

// Build Centre home (Build preview artboard): three rooms lit from the records (GET /api/company/build/home, sh_platform/build/home.py).
// Room 1 always open; room 2 next once the blueprint is signed; room 3 open once the run log has runs; a locked room is dim with no action.

export type LoadState = "loading" | "error" | "refused" | "populated";

/** Loading, error and refused for the three Build screens, drawn with the design system. */
export function BuildState({ state, onRetry, children }: { state: LoadState; onRetry?: () => void; children: ReactNode }) {
  if (state === "populated") return <>{children}</>;
  if (state === "loading") return <div role="status" aria-busy="true"><EmptyState title="Reading the build records" lines={["This takes a moment."]} /></div>;
  if (state === "refused") return <div role="alert"><EmptyState title="The Build centre is not open to you" lines={[copy.states.refused]} /></div>;
  return (
    <div role="alert">
      <EmptyState title="Not available yet" lines={[copy.states.error]} />
      {onRetry ? <Button onClick={onRetry}>{copy.states.retry}</Button> : null}
    </div>
  );
}

/** Fetch once per attempt; `retry` starts another. */
export function useLoad<T>(path: string): { data: T | null; state: LoadState; retry: () => void; setData: (d: T) => void } {
  const [data, setData] = useState<T | null>(null);
  const [state, setState] = useState<LoadState>("loading");
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let live = true;
    apiGet<T>(path)
      .then((d) => { if (live) { setData(d); setState("populated"); } })
      .catch((e: unknown) => { if (live) setState(e instanceof Refused ? "refused" : "error"); });
    return () => { live = false; };
  }, [path, attempt]);
  const retry = useCallback(() => { setState("loading"); setAttempt((n) => n + 1); }, []);
  return { data, state, retry, setData };
}

type RoomState = "open" | "next" | "locked";
interface Room1 { room: 1; state: RoomState; environment: { confirmed: number; of: number }; blueprint: { state: "signed" | "draft" | "none"; signed_by: string[]; signed_at: string | null }; detail: string[] }
interface Room2 { room: 2; state: RoomState; pipelines: { sources: number; last_run: { ok: number; late: number; failed: number } }; proven: { match: number; gap: number; not_yet: number; uat_signed: number }; release: string; detail: string[] }
interface Room3 { room: 3; state: RoomState; today: { late: number; failed: number; open_alerts: number }; detail: string[] }
export interface BuildHome { rooms: [Room1, Room2, Room3]; room0?: { state: RoomState; handed_over_from: { id: string; title: string | null; at: string | null; by: string | null } | null } }

const LIT = { open: "open", next: "next", locked: "dim" } as const;
const WORD = { open: "Open", next: "Next", locked: "Not yet" } as const;
/** 2026-06-12 -> 12 June 2026 (the signed date, read as a person says it). */
export const day = (iso: string) => new Date(`${iso.slice(0, 10)}T00:00:00Z`).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" });

function Room({ n, name, state, line, counts, detail, action }: { n: number; name: string; state: RoomState; line: string; counts: string[]; detail?: string[]; action: { label: string; href: string } }) {
  return (
    <li style={{ display: "flex", flexDirection: "column", gap: "var(--ds-s2)", minWidth: 0 }}>
      <RoomTile number={n} name={name} state={LIT[state]} line={line} counts={[WORD[state], ...counts]} action={state === "locked" ? undefined : action} />
      {detail?.length ? (
        <SideCard title="What is late and what waits">
          <ul aria-label={`${name}: what is late and what waits`}>{detail.map((d) => <li key={d}>{d}</li>)}</ul>
        </SideCard>
      ) : null}
    </li>
  );
}

export default function BuildCentre() {
  const { data, state, retry } = useLoad<BuildHome>("/api/company/build/home");
  const [r1, r2, r3] = data?.rooms ?? [];
  const bp = r1?.blueprint;
  const from = data?.room0?.handed_over_from;
  return (
    <PageFrame
      crumbs="Build centre"
      title="Turn the signed catalogue into working data."
      subline="The inputs are the signed gap report, the governed catalogue and full extracts. People approve twice per source: the design, and the first numbers that match the report."
      actions={<><Chip>from: signed gap report</Chip><Chip>to: numbers that match</Chip><Chip href="/centre/build/architecture">Architecture</Chip></>}
      aside={r1 && r2 ? (
        <>
          <SideCard title="Environment check" action={{ label: "Open", href: "/centre/build/environment" }}>
            <p>{r1.environment.confirmed} of {r1.environment.of} answers confirmed. Where the warehouse lives, the scheduler, where files arrive and where alerts go.</p>
          </SideCard>
          <SideCard title="Your approvals">
            <ul>
              <li>The design: {bp?.state === "signed" ? `signed by ${bp.signed_by.join(", ") || "the head of data"}${bp.signed_at ? ` on ${day(bp.signed_at)}` : ""}` : bp?.state === "draft" ? "waits for the head of data" : "no blueprint yet"}</li>
              <li>The first numbers that match: release {r2.release}</li>
            </ul>
          </SideCard>
          <Footnote>Every count here is read from the company's own build records.</Footnote>
        </>
      ) : undefined}
    >
      <ChainPanel />
      <BuildState state={state} onRetry={retry}>
        {r1 && r2 && r3 ? (
          <ul aria-label="The rooms" style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: "var(--ds-s2)", gridTemplateColumns: DOORS_GRID, alignItems: "start" }}>
            <Room n={0} name={brCopy.room0.name} state="open" line={brCopy.room0.line} counts={[from ? brCopy.fromHome(from.title ?? "an Initiative") : "Opens when an Initiative is handed to Build"]}
              action={{ label: brCopy.room0.action, href: from ? `/centre/build/gap-analysis?from=${from.id}` : "/centre/build/gap-analysis" }} />
            <Room n={1} name="Architect your design" state={r1.state} detail={r1.detail}
              line="The Architect drafts the model, the lineage into each system, the quality rules the scan found and the access rules from the seals. The head of data signs the design."
              counts={[`${r1.environment.confirmed} of ${r1.environment.of} confirmed`, `Blueprint ${bp?.state === "signed" ? `signed by ${bp.signed_by.join(", ") || "the head of data"}` : bp?.state ?? "none"}`]}
              action={bp?.state === "none" ? { label: "Confirm the environment", href: "/centre/build/environment" } : { label: "Review the blueprint", href: "/centre/build/blueprint" }} />
            <Room n={2} name="Build the data" state={r2.state} detail={r2.detail}
              line="Pipelines are built from the signed design and run on full extracts; every measure is tested against the reported figure. Opens when the blueprint is signed."
              counts={[`Pipelines: ${r2.pipelines.sources} sources; last run ${r2.pipelines.last_run.ok} ok, ${r2.pipelines.last_run.late} late, ${r2.pipelines.last_run.failed} failed`,
                `Measures proven: ${r2.proven.match} match, ${r2.proven.gap} gap, ${r2.proven.not_yet} not yet; UAT signed ${r2.proven.uat_signed}`, `Release ${r2.release}`]}
              action={{ label: "Run the pipelines", href: "/centre/build/pipelines" }} />
            <Room n={3} name="Ops manager" state={r3.state} detail={r3.detail}
              line="The operations monitor checks each run and tells the owner, in plain words, when a file is late or a rule fails."
              counts={[`${r3.today.open_alerts} open alert${r3.today.open_alerts === 1 ? "" : "s"}`, ...(r3.today.late || r3.today.failed ? [`today: ${r3.today.late} late, ${r3.today.failed} failed`] : [])]}
              action={{ label: "Open Ops", href: "/centre/build/ops" }} />
          </ul>
        ) : null}
      </BuildState>
    </PageFrame>
  );
}
