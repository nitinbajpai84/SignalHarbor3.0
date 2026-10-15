import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError } from "../../api/client";
import { Button, Chip, PageFrame, Pill, type PillTone } from "../../design";
import { dismissItem, getPulse, takeCase, type PulseItem, type PulseList } from "./api";

// E5c: /centre/today, the Daily Pulse. Every status is a written word, never colour alone.
const plain = (err: unknown) => (err instanceof ApiError && err.message ? err.message : "That did not go through. Please try again.");
export const statusTone = (s: string): PillTone => {
  const w = s.toLowerCase();
  return w.startsWith("official") ? "signed" : w.startsWith("stale") || w.startsWith("unverified") || w.startsWith("break") || w.startsWith("limit") || w.startsWith("late") ? "late" : w.startsWith("revised") ? "draft" : "open";
};

// skipKinds: a page that shows these cards in its own sections (Action shows assignments) leaves them out here.
export default function TodayPage({ framed = false, skipKinds = [] }: { framed?: boolean; skipKinds?: string[] }) {
  const [data, setData] = useState<PulseList | null>(null);
  const [role, setRole] = useState("");
  const [filter, setFilter] = useState<"needs" | "look">("needs");
  const [error, setError] = useState("");
  const [dismissing, setDismissing] = useState<string | null>(null);
  const [reason, setReason] = useState("");

  const load = useCallback((r: string) => {
    setError("");
    getPulse(r).then((d) => { setData(d); setRole(d.role); }).catch((e) => { setData({ role: r, roles: [], items: [] }); setError(plain(e)); });
  }, []);
  useEffect(() => { load(""); }, [load]);

  async function act(fn: () => Promise<unknown>) {
    setError("");
    try { await fn(); setDismissing(null); load(role); } catch (e) { setError(plain(e)); }
  }
  const shown = (data?.items ?? []).filter((i) => !skipKinds.includes(i.kind ?? "") && (filter === "needs" ? i.needs_me : !i.needs_me));

  // UX-04: inside the Action centre the frame already carries the title, so Today drops its own.
  const body = (
    <>
      <div style={{ display: "flex", gap: 8, margin: "8px 0 16px" }} role="group" aria-label="Filter">
        <Chip tone={filter === "needs" ? "active" : "default"} onClick={() => setFilter("needs")}>Needs me</Chip>
        <Chip tone={filter === "look" ? "active" : "default"} onClick={() => setFilter("look")}>Worth a look</Chip>
      </div>
      {error ? <p role="alert">{error}</p> : null}
      {data === null ? <p className="ds-muted" role="status">Loading today.</p> : shown.length === 0 && !error ? (
        <p className="ds-muted">{filter === "needs" ? "Nothing needs you today." : "Nothing else worth a look."}</p>) : (
        <ul style={{ listStyle: "none", padding: 0, display: "grid", gap: 12 }}>
          {shown.map((i: PulseItem) => (
            <li key={i.id} className="ds-card" style={{ padding: 16 }}>
              <Pill tone={statusTone(i.status)}>{i.status}</Pill>
              <h2 style={{ margin: "8px 0 4px", fontSize: "1rem" }}>{i.headline}</h2>
              <p className="ds-muted" style={{ margin: 0 }}>
                {[i.valued && `${i.valued_label ?? "As of"} ${i.valued}`, i.received && `received ${i.received}`, i.affected].filter(Boolean).join(" · ")}
              </p>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 12 }}>
                {i.link ? <Link className="ds-link" to={i.link}>{i.action ?? "Open"}</Link> : null}
                {i.case_id ? <Button variant="primary" onClick={() => void act(() => takeCase(i.case_id as string))}>Take case</Button> : null}
                <button type="button" className="ds-link" style={{ marginLeft: "auto", background: "none", border: 0, padding: 0, cursor: "pointer", font: "inherit" }}
                  onClick={() => { setDismissing(i.id); setReason(""); }}>Not for me</button>
              </div>
              {dismissing === i.id ? (
                <form style={{ display: "flex", gap: 8, marginTop: 8 }} onSubmit={(e) => {
                  e.preventDefault();
                  if (reason.trim()) void act(() => dismissItem(i.id, reason.trim()));
                }}>
                  <input className="ds-input" aria-label="Reason for dismissing" placeholder="Why is this not needed?" value={reason} onChange={(e) => setReason(e.target.value)} style={{ flex: 1 }} />
                  <Button type="submit" disabled={!reason.trim()}>Dismiss with reason</Button>
                </form>) : null}
            </li>))}
        </ul>)}
    </>
  );
  return framed
    ? <div className="ds-frame" style={{ paddingTop: 0 }}><section className="ds-frame__main">{body}</section></div>
    : <PageFrame title="Today" subline="What changed, what it affects, and what is waiting for you.">{body}</PageFrame>;
}
