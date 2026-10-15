import { useContext } from "react";
import { Link } from "react-router-dom";

import { InStepper } from "../b9/context";

import "../b7/studio.css";
import { counts, useFacts, type Facts } from "./useFacts";

// BC1: the three places where people build. Three large tiles, each with a small drawn mark, its purpose in one line and a live count.
export type Room = "pipelines" | "dashboards" | "architecture";
const TILES: { room: Room; name: string; line: string; mark: "flow" | "grid" | "layers" }[] = [
  { room: "architecture", name: "Architecture", line: "The three layers, every table, and how they connect. Ask Span.", mark: "layers" },
  { room: "pipelines", name: "Pipelines", line: "Sources flow through bronze and silver to gold. Run, schedule, go live.", mark: "flow" },
  { room: "dashboards", name: "Dashboard studio", line: "Arrange widgets on a grid, send for approval, publish to Consume.", mark: "grid" },
];

function Mark({ kind }: { kind: "flow" | "grid" | "layers" }) {
  const c = { fill: "none", stroke: "currentColor", strokeWidth: 2, strokeLinecap: "round" as const };
  return (
    <svg className="b8-mark" viewBox="0 0 64 40" width="64" height="40" aria-hidden="true" focusable="false">
      {kind === "flow" ? <><circle cx="8" cy="20" r="5" {...c} /><circle cx="32" cy="10" r="5" {...c} /><circle cx="32" cy="30" r="5" {...c} /><circle cx="56" cy="20" r="5" {...c} className="b8-pulse" />
        <path d="M13 20 L27 10 M13 20 L27 30 M37 10 L51 20 M37 30 L51 20" {...c} /></> : null}
      {kind === "grid" ? <><rect x="4" y="4" width="26" height="14" rx="3" {...c} /><rect x="34" y="4" width="26" height="14" rx="3" {...c} /><rect x="4" y="22" width="16" height="14" rx="3" {...c} /><rect x="24" y="22" width="36" height="14" rx="3" {...c} className="b8-pulse" /></> : null}
      {kind === "layers" ? <><path d="M32 4 L58 14 L32 24 L6 14 Z" {...c} className="b8-pulse" /><path d="M6 22 L32 32 L58 22" {...c} /><path d="M6 30 L32 40 L58 30" {...c} opacity="0.5" /></> : null}
    </svg>
  );
}

export default function RoomSwitcher({ pid, current, facts, base = "/centre/build" }: { pid: string; current?: Room; facts: Facts | null; base?: string }) {
  if (useContext(InStepper)) return null; // V5: the step rail does this job
  const c = facts?.ready ? counts(facts) : null;
  const to = (r: Room) => `${base}/p/${encodeURIComponent(pid)}/${r}`;
  return (
    <nav className="b8-rooms" aria-label="Build rooms">
      {TILES.map((t) => (
        <Link key={t.room} to={to(t.room)} className="b8-tile" aria-current={current === t.room ? "page" : undefined} data-room={t.room}>
          <Mark kind={t.mark} />
          <span className="b8-tile-name">{t.name}</span>
          <span className="b8-tile-line">{t.line}</span>
          <span className="b8-tile-count">{c ? c[t.room] : "Counting"}</span>
        </Link>))}
    </nav>
  );
}

/** The switcher for pages that do not already hold the facts (the plan page, the project list). */
export function ProjectRooms({ pid, current }: { pid: string; current?: Room }) {
  return <RoomSwitcher pid={pid} current={current} facts={useFacts(pid)} />;
}
