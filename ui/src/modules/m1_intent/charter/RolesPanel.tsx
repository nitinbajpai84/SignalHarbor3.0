import { useEffect, useState } from "react";

import { ApiError, apiGet, apiSend } from "../../../api/client";
import { Button, SideCard } from "../../../design";

type Role = "architect" | "developer" | "tester" | "sponsor" | "ops" | "informed";
interface Mark { mark: "stated" | "guessed" | "unknown"; by: string; from: string }
interface Roles { roles: Record<Role, string | string[] | null>; provenance: Partial<Record<Role, Mark>>; can_edit: boolean }

const LABELS: [Role, string][] = [["architect", "Architect"], ["developer", "Developer"], ["tester", "Tester"], ["sponsor", "Sponsor"], ["ops", "Operations"], ["informed", "Kept informed"]];
const text = (v: string | string[] | null | undefined) => (Array.isArray(v) ? v.join(", ") : v ?? "");
const field = { minHeight: 44, padding: "8px 12px", borderRadius: 8, font: "inherit", fontSize: 13, flex: "1 1 140px" } as const;

/** The six build roles named at the charter: each with who, whether Lens guessed or a person stated it, and where it came from.
 * Only the organiser edits. Render it once from the charter screen: <RolesPanel sessionId={sessionId} />. */
export default function RolesPanel({ sessionId }: { sessionId: string }) {
  const url = `/api/modules/m1_intent/sessions/${sessionId}/roles`;
  const [data, setData] = useState<Roles | null>(null);
  const [editing, setEditing] = useState<Role | null>(null);
  const [draft, setDraft] = useState("");
  const [problem, setProblem] = useState<string | null>(null);

  useEffect(() => {
    apiGet<Roles>(url).then((d) => { if (d && d.roles && d.provenance) setData(d); }).catch(() => setProblem("The roles could not be loaded. Please try again."));
  }, [url]);

  async function save(role: Role, confirm?: string) {
    const raw = confirm ?? draft;
    const value = role === "informed" ? raw.split(",").map((s) => s.trim()).filter(Boolean) : raw.trim() || null;
    try {
      setData(await apiSend<Roles>("PUT", url, { [role]: value }));
      setEditing(null);
      setProblem(null);
    } catch (e) {
      setProblem(e instanceof ApiError && e.message ? e.message : "That could not be saved. Please try again.");
    }
  }

  // who named the roles is said once at the top when one person named them all; each line then only says stated, left open or guessed
  const stated = data ? Object.values(data.provenance).filter((m): m is Mark => m?.mark === "stated") : [];
  const oneBy = stated.length > 0 && stated.every((m) => m.by === stated[0]!.by) ? stated[0]! : null;
  return (
    <SideCard title="Who does what">
      {problem ? <p role="alert" className="ds-warn">{problem}</p> : null}
      {oneBy ? <p className="ds-soft" style={{ margin: 0 }}>{`Named by ${oneBy.by}${oneBy.from === "Set by the organiser" ? ", the organiser" : ""}.`}</p> : null}
      {data ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {LABELS.map(([role, label]) => {
            const p = data.provenance[role];
            const value = text(data.roles[role]);
            return (
              <div key={role} data-role={role} style={{ display: "flex", flexDirection: "column", gap: 2, fontSize: 13 }}>
                <span className="ds-muted">{label}</span>
                {editing === role ? (
                  <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                    <input aria-label={label} className="ds-btn" style={field} value={draft} onChange={(e) => setDraft(e.target.value)} />
                    <Button variant="primary" onClick={() => void save(role)}>Save</Button>
                    <Button onClick={() => setEditing(null)}>Cancel</Button>
                  </div>
                ) : (
                  <div style={{ display: "flex", gap: 8, alignItems: "center", justifyContent: "space-between" }}>
                    <strong className={value ? undefined : "ds-muted"}>{value || "Not named yet"}</strong>
                    {data.can_edit && value && p?.mark === "guessed" ? <Button variant="primary" aria-label={`Confirm ${label}`} onClick={() => void save(role, value)}>Confirm</Button> : null}
                    {data.can_edit ? <Button aria-label={`Edit ${label}`} onClick={() => { setEditing(role); setDraft(value); }}>Edit</Button> : null}
                  </div>
                )}
                {p ? <span data-mark={p.mark} className={p.mark === "stated" ? "ds-soft" : "ds-warn"}>{p.mark !== "stated" ? `Guessed. ${p.from}` : `${value ? "Stated" : "Left open"}${oneBy ? "" : ` by ${p.by}. ${p.from}`}`}</span> : null}
              </div>
            );
          })}
        </div>
      ) : problem ? null : <p role="status" className="ds-muted">Reading who does what.</p>}
      <p>These people get the Build hand-overs in their Pulse.</p>
    </SideCard>
  );
}
