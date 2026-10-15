import { useEffect, useState } from "react";

import AccessCard from "../k1/AccessCard";
import type { AccessRequest } from "../k1/api";
import { answerProjectRequest, getProjectAccess, isLock } from "./api";

// G1: the owner's Approve / Not now card in Pulse: K1's card, answering through the project's own call.
export default function ProjectAccessCard({ pid, title, onDone }: { pid: string; title: string; onDone: () => void }) {
  const [rows, setRows] = useState<AccessRequest[] | null>(null);
  useEffect(() => {
    let live = true;
    getProjectAccess(pid).then((d) => {
      if (!live || isLock(d)) return;
      setRows(d.requests.map((r) => ({
        id: r.id, item_id: pid, item_name: title, requester: r.requester, to: "", owner_left: false, reason: r.reason, at: r.at,
        state: "requested", decided_by: null, decision_note: "", expires: null,
      })));
    }, () => { if (live) setRows([]); });
    return () => { live = false; };
  }, [pid, title]);
  if (!rows) return <p className="ds-muted">Loading the request…</p>;
  return <>{rows.map((r) => <AccessCard key={r.id} req={r} onDone={onDone} answer={(approve, days) => answerProjectRequest(pid, r.id, approve, days)} />)}</>;
}
