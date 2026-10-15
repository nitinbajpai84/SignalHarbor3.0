import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { apiGet } from "../api/client";
import { useLoad } from "../components/useLoad";
import ScreenState from "../components/ScreenState";
import { Button, Chip } from "../design";
import { peopleCopy as t, postPeople, say, type PeopleData } from "./PeoplePanel";
import "./StageClock.css";

interface Company { people: { person_id: string; ref?: string; name: string; role: string | null; area: string | null }[]; areas: { id: string; name: string; count: number }[] }

const dt = {
  title: "Invite people",
  pick: "Pick from your company",
  search: "Search by name",
  nobody: "No one matches. Use a link instead.",
  picked: "Picked",
  roleFor: (n: string) => `Role for ${n}`,
  decider: "Decider",
  owner: "Owner",
  chooseDecider: "Choose a decider.",
  chooseOwner: "Choose an owner, or let North suggest one.",
  areas: "Tell people in these areas",
  noAreas: "No areas chosen. Choose areas on the first screen.",
  areaCount: (n: number) => `${n} ${n === 1 ? "person" : "people"}`,
  send: "Send invitations",
  link: "Use a join link instead",
};

/** Roles by type for a person picked here: Decision picks advisers, Problem picks an owner when none is named, else affected. */
function defaultRole(type: string, allowed: string[], hasOwner: boolean): string {
  const want = type === "decision" ? "adviser" : type === "problem" ? (hasOwner ? "affected" : "owner") : "participant";
  return allowed.includes(want) ? want : allowed[0] ?? "participant";
}

/** Screen C: a dialog over the panel or the people view. Nothing is written until "Send invitations". */
export default function InviteDialog({ intentId, data, onClose, onDone }: { intentId: string; data: PeopleData; onClose: () => void; onDone: () => void }) {
  const nav = useNavigate();
  const company = useLoad(() => apiGet<Company>("/api/intents/people"), "company");
  const type = data.intent.type;
  const slot = type === "decision" ? "decider" : type === "problem" ? "owner" : null;
  const named = new Set(data.people.filter((p) => p.status !== "removed" && p.status !== "declined").map((p) => p.person_id));
  const hasOwner = data.people.some((p) => p.role === "owner" && p.status !== "declined" && p.status !== "removed");
  const [q, setQ] = useState("");
  const [roles, setRoles] = useState<Record<string, string>>({});
  const [areas, setAreas] = useState<string[]>([]);
  const [slotId, setSlotId] = useState("");
  const [problem, setProblem] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const fallback = defaultRole(type, data.roles_allowed, hasOwner);

  const list = company.data?.people ?? [];
  const shown = useMemo(() => list.filter((p) => !named.has(p.ref ?? p.person_id) && p.name.toLowerCase().includes(q.trim().toLowerCase())), [list, q, named]);
  const ids = Object.keys(roles);
  const have = ids.length + data.people.filter((p) => !["removed", "declined", "affected"].includes(p.status ?? "") && p.role !== "organiser").length;
  const toggle = (id: string) => setRoles((r) => { const n = { ...r }; if (id in n) delete n[id]; else n[id] = fallback; return n; });
  const send = () => {
    setBusy(true);
    postPeople(intentId, { people: ids.map((person_id) => ({ person_id, role: roles[person_id] })), areas, ...(slot && slotId ? { [slot]: slotId } : {}) })
      .then(onDone, (e) => { setProblem(say(e)); setBusy(false); });
  };
  const nameOf = (id: string) => list.find((p) => p.person_id === id)?.name ?? "";

  return (
    <div className="scx-back">
      <div role="dialog" aria-modal="true" aria-label={dt.title} className="ds-card scx" style={{ width: "min(560px, 100%)", boxSizing: "border-box", alignContent: "start" }}>
        <h2>{dt.title}</h2>
        <label className="sc__note">{dt.pick}
          <input type="search" aria-label={dt.search} placeholder={dt.search} value={q} onChange={(e) => setQ(e.target.value)} style={{ width: "100%", boxSizing: "border-box", minHeight: 44 }} />
        </label>
        <ScreenState state={company.state} message={company.message} onRetry={company.retry}>
          {shown.length === 0 ? <p className="n-muted">{dt.nobody}</p> : (
            <ul style={{ listStyle: "none", margin: 0, padding: 0, maxHeight: 200, overflow: "auto", display: "grid", gap: 4 }}>
              {shown.map((p) => (
                <li key={p.person_id}>
                  <label style={{ display: "flex", gap: "var(--ds-s1)", alignItems: "center", minHeight: 44 }}>
                    <input type="checkbox" checked={p.person_id in roles} onChange={() => toggle(p.person_id)} />
                    <span>{p.name}{p.role || p.area ? <span className="n-muted"> {[p.role, p.area].filter(Boolean).join(", ")}</span> : null}</span>
                  </label>
                </li>
              ))}
            </ul>
          )}
        </ScreenState>
        {ids.length ? (
          <div aria-label={dt.picked} style={{ display: "grid", gap: 4 }}>
            {ids.map((id) => (
              <span key={id} style={{ display: "flex", gap: "var(--ds-s1)", alignItems: "center", flexWrap: "wrap" }}>
                <Chip tone="active" onClick={() => toggle(id)}>{nameOf(id)}</Chip>
                <select aria-label={dt.roleFor(nameOf(id))} value={roles[id]} onChange={(e) => setRoles({ ...roles, [id]: e.target.value })} style={{ minHeight: 44 }}>
                  {data.roles_allowed.map((r) => <option key={r} value={r}>{t.role[r]}</option>)}
                </select>
              </span>
            ))}
          </div>
        ) : null}
        {slot ? (
          <label className="sc__note">{slot === "decider" ? dt.decider : dt.owner}
            <select value={slotId} onChange={(e) => setSlotId(e.target.value)} style={{ width: "100%", minHeight: 44 }}>
              <option value="">{slot === "decider" ? dt.chooseDecider : dt.chooseOwner}</option>
              {list.filter((p) => !named.has(p.ref ?? p.person_id)).map((p) => <option key={p.person_id} value={p.person_id}>{p.name}</option>)}
            </select>
          </label>
        ) : null}
        <fieldset className="scx__days" style={{ alignContent: "flex-start" }}>
          <legend className="sc__note">{dt.areas}</legend>
          {data.intent.areas.length === 0 ? <span className="n-muted">{dt.noAreas}</span> : data.intent.areas.map((a) => {
            const n = company.data?.areas.find((x) => x.id === a.id)?.count;
            return <Chip key={a.id} tone={areas.includes(a.id) ? "active" : "default"} onClick={() => setAreas(areas.includes(a.id) ? areas.filter((x) => x !== a.id) : [...areas, a.id])}>{a.name}{n === undefined ? "" : `, ${dt.areaCount(n)}`}</Chip>;
          })}
        </fieldset>
        {data.range ? <p className="sc__note">{t.suggestion} {t.rangeNote(data.range.low, data.range.high, have)}</p> : null}
        {problem ? <p role="alert" className="sc__err">{problem}</p> : null}
        <div className="scx__buttons">
          <Button variant="primary" disabled={busy || (ids.length === 0 && !slotId && areas.length === 0)} onClick={send}>{dt.send}</Button>
          <Button onClick={() => nav(`/centre/intent/${intentId}/people`)}>{dt.link}</Button>
          <Button onClick={onClose}>{t.cancel}</Button>
        </div>
      </div>
    </div>
  );
}
