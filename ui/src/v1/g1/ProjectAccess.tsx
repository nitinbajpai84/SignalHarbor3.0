import { useCallback, useEffect, useState } from "react";

import { ApiError } from "../../api/client";
import { Pill } from "../../design";
import AccessCard from "../k1/AccessCard";
import type { Sensitivity } from "../k1/api";
import { answerProjectRequest, getProjectAccess, isLock, setSensitivity, type Access } from "./api";

// UC9-08: the words follow g1_access.level (team plus company administrators read in full).
// G1: the access answer in the project header: Open, Internal or Restricted, and the team. The owner (or a company admin) gets a small control.
// NU-16: a request to read the project reaches its owner as a comment on this page; the owner answers it right here (Approve / Not now),
// which also answers and closes that comment.
const WORDS: Record<Sensitivity, { name: string; line: string }> = {
  open: { name: "Open", line: "Everyone in the company can read this project." },
  internal: { name: "Internal", line: "Only the team and company administrators can read this project. Others see its title and ask for access." },
  restricted: { name: "Restricted", line: "Only the team and company administrators can read this project. Others do not see it at all." },
};

export default function ProjectAccess({ pid, name }: { pid: string; name?: string }) {
  const [a, setA] = useState<Access | null>(null);
  const [error, setError] = useState("");
  const load = useCallback(() => {
    getProjectAccess(pid).then((d) => setA(!isLock(d) && Array.isArray(d.team) && d.sensitivity in WORDS ? d : null), () => setA(null));
  }, [pid]);
  useEffect(load, [load]);
  if (!a) return null;
  const w = WORDS[a.sensitivity];
  const change = (s: Sensitivity) => {
    setError("");
    setSensitivity(pid, s).then(load, (e: unknown) => setError(e instanceof ApiError && e.message ? e.message : "That did not go through. Please try again."));
  };
  return (
    <div aria-label="Who can see this project" role="group" style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center", marginBottom: 12 }}>
      <Pill tone={a.sensitivity === "open" ? "open" : "restricted"}>{w.name}</Pill>
      <span className="ds-muted">{w.line}</span>
      {a.team.length ? <span className="ds-muted">Team: {a.team.map((m) => m.name).join(", ")}.</span> : null}
      {a.can_manage ? (
        <label style={{ fontSize: 13 }}>Change{" "}
          <select aria-label="Change who can see this project" value={a.sensitivity} onChange={(e) => change(e.target.value as Sensitivity)}>
            <option value="open">Open</option><option value="internal">Internal</option><option value="restricted">Restricted</option>
          </select>
        </label>
      ) : null}
      {error ? <p role="alert" style={{ margin: 0 }}>{error}</p> : null}
      {(a.requests ?? []).length ? (
        <section aria-label="Requests to read this project" style={{ flexBasis: "100%" }}>
          {a.requests.map((r) => (
            <AccessCard key={r.id} onDone={load} answer={(approve, days) => answerProjectRequest(pid, r.id, approve, days)}
              req={{ id: r.id, item_id: pid, item_name: name ?? "this project", requester: r.requester, to: "", owner_left: false, reason: r.reason, at: r.at,
                state: "requested", decided_by: null, decision_note: "", expires: null }} />))}
        </section>) : null}
    </div>
  );
}
