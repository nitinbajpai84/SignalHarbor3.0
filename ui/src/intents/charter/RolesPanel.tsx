import { useCallback, useEffect, useState } from "react";

import { ApiError, apiGet, apiSend } from "../../api/client";
import { Button, Pill, SideCard } from "../../design";
import { rolesCopy as t } from "./charterCopy";

// Files 32 and 34: the six Build roles named at the charter, and the page a named person answers on.
// Reshaped from ui/src/modules/m1_intent/charter/RolesPanel.tsx: a people picker in place of free text, an answer chip, Ask them, Name someone else.

export type RoleKey = "architect" | "developer" | "tester" | "sponsor" | "ops" | "informed";
export interface RoleRow {
  role: RoleKey; label: string; duty: string; required: boolean; person_ids: string[]; person: string | null; mark: string; mark_reason: string | null;
  unresolved?: string | null; answer: { state: string; at: string | null; asked_at: string | null; reason?: string | null };
}
export interface Person { id: string; name: string; role: string | null }
export interface RolesData { rows: RoleRow[]; footer: string; people: Person[]; mine?: RoleKey[]; asked?: RoleKey[] }
export interface RoleRequestData {
  intent: { id: string; title: string; purpose: string | null; ends: string | null }; organiser: string | null; mine: RoleRow[]; others: RoleRow[]; handed_over: boolean;
}

const day = (iso: string | null) => (iso ? new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short" }) : "");
const problemText = (e: unknown) => (e instanceof ApiError && e.status !== 0 && e.status < 500 && e.message ? e.message : t.failed);
const tone = (s: string) => (s === "accepted" || s === "seen" ? "ok" : s === "declined" ? "late" : "draft");

/** "Who does what": six rows, a mark chip and an answer chip each. The organiser edits (each change saves at once); everyone else reads. */
export default function RolesPanel({ intentId, canEdit, onChange }: { intentId: string; canEdit: boolean; onChange?: () => void }) {
  const url = `/api/intents/${intentId}/roles`;
  const [data, setData] = useState<RolesData | null>(null);
  const [editing, setEditing] = useState<RoleKey | null>(null);
  const [pick, setPick] = useState<string[]>([]);
  const [problem, setProblem] = useState<string | null>(null);

  useEffect(() => {
    apiGet<RolesData>(url).then(setData).catch((e: unknown) => setProblem(problemText(e)));
  }, [url]);

  const run = useCallback(async (work: () => Promise<RolesData>) => {
    try {
      setData(await work());
      setEditing(null);
      setProblem(null);
      onChange?.();
    } catch (e) {
      setProblem(problemText(e));
    }
  }, [onChange]);
  const put = (changes: Record<string, string | string[] | null>) => run(() => apiSend<RolesData>("PUT", url, changes));
  const ask = (roles?: RoleKey[]) => run(() => apiSend<RolesData>("POST", `${url}/ask`, roles ? { roles } : {}));

  const rows = data?.rows ?? [];
  const toAsk = rows.filter((r) => r.person && r.mark === "Stated" && r.answer.state === "not_asked").map((r) => r.role);
  const named = rows.filter((r) => r.person).length;
  const count = (s: string) => rows.filter((r) => r.person && r.answer.state === s).length;
  const gaps = rows.filter((r) => ["architect", "developer", "tester"].includes(r.role) && !r.person);
  const edit = (r: RoleRow) => { setEditing(r.role); setPick(r.person_ids); };

  return (
    <SideCard title={t.title}>
      <p className="ds-soft" style={{ margin: 0 }}>{t.sub}</p>
      {problem ? <p role="alert" className="ds-warn" style={{ margin: 0 }}>{problem}</p> : null}
      {!data && !problem ? <p role="status" className="ds-muted">Reading who does what.</p> : null}
      {rows.map((r) => (
        <div key={r.role} data-role={r.role} className="ch-role">
          <span className="ds-muted">{r.label}</span>
          <span className="ch-role__duty">{t.willBeAsked}: {r.duty}</span>
          {editing === r.role ? (
            <div className="ch-row">
              {r.role === "informed" ? (
                <fieldset className="ch-people" aria-label={t.pickFor(r.label)}>
                  {data!.people.map((p) => (
                    <label key={p.id}><input type="checkbox" checked={pick.includes(p.id)} onChange={() => setPick(pick.includes(p.id) ? pick.filter((x) => x !== p.id) : [...pick, p.id])} /> {p.name}{p.role ? ` (${p.role})` : ""}</label>
                  ))}
                </fieldset>
              ) : (
                <select aria-label={t.pickFor(r.label)} className="ds-btn" value={pick[0] ?? ""} onChange={(e) => setPick(e.target.value ? [e.target.value] : [])}>
                  <option value="">{t.pick}</option>
                  {data!.people.map((p) => <option key={p.id} value={p.id}>{p.name}{p.role ? ` (${p.role})` : ""}</option>)}
                </select>
              )}
              <Button variant="primary" onClick={() => void put({ [r.role]: r.role === "informed" ? pick : pick[0] ?? null })}>{t.save}</Button>
              {r.role !== "sponsor" ? <Button onClick={() => void put({ [r.role]: r.role === "informed" ? [] : null })}>{t.clear}</Button> : null}
              <Button onClick={() => setEditing(null)}>{t.cancel}</Button>
            </div>
          ) : (
            <div className="ch-row">
              <strong className={r.person ? undefined : "ds-muted"}>{r.person ?? (r.unresolved ? t.notInList : t.notNamed)}</strong>
              {canEdit && r.person && r.mark === "Guessed" ? <Button variant="primary" aria-label={`${t.confirm} ${r.label}`} onClick={() => void put({ [r.role]: r.role === "informed" ? r.person_ids : r.person_ids[0]! })}>{t.confirm}</Button> : null}
              {canEdit && r.role !== "sponsor" ? <Button aria-label={`${t.edit} ${r.label}`} onClick={() => edit(r)}>{t.edit}</Button> : null}
              {canEdit && r.person && r.mark === "Stated" && r.answer.state === "not_asked" ? <Button aria-label={`${t.ask} ${r.label}`} onClick={() => void ask([r.role])}>{t.ask}</Button> : null}
              {canEdit && r.answer.state === "declined" ? <Button aria-label={`${t.nameElse} ${r.label}`} onClick={() => edit(r)}>{t.nameElse}</Button> : null}
            </div>
          )}
          <div className="ch-row">
            <span data-mark={r.mark} className={r.mark === "Guessed" ? "ds-warn" : "ds-soft"}>{r.mark}{r.mark_reason ? `. ${r.mark_reason}` : ""}</span>
            {r.person ? (
              <span title={r.answer.reason ?? undefined}><Pill tone={tone(r.answer.state)}>{t.answers[r.answer.state] ?? r.answer.state}{r.answer.at ? ` ${day(r.answer.at)}` : ""}</Pill></span>
            ) : null}
          </div>
          {r.answer.state === "declined" && r.answer.reason ? <p className="ds-warn" style={{ margin: 0 }}>{r.answer.reason}</p> : null}
        </div>
      ))}
      {data && named > 0 ? <p className="ds-muted" style={{ margin: 0 }}>{t.counts(named, count("accepted"), count("waiting"), count("declined"))}</p> : null}
      {data?.footer ? <p className="ds-soft" style={{ margin: 0 }}>{data.footer}</p> : null}
      {canEdit && gaps.length > 0 ? (
        <button type="button" className="ch-link" onClick={() => edit(gaps[0]!)}>
          {`The Build-ready check needs a ${gaps.map((g) => g.label.toLowerCase()).join(" and a ")}. ${gaps.length === 1 ? "It is not named." : "Neither is named."}`}
        </button>
      ) : null}
      {canEdit ? <div><Button disabled={toAsk.length === 0} onClick={() => void ask()}>{toAsk.length ? `${t.askAll} (${toAsk.length})` : t.askAll}</Button>{toAsk.length === 0 ? <span className="ds-muted"> {t.nobody}</span> : null}</div> : null}
    </SideCard>
  );
}

/** Screen B of file 34: what the named person sees, and the buttons that answer for their own role only. */
export function RoleRequest({ intentId, data, onAnswered }: { intentId: string; data: RoleRequestData; onAnswered: () => void }) {
  const [declining, setDeclining] = useState<RoleKey | null>(null);
  const [reason, setReason] = useState("");
  const [problem, setProblem] = useState<string | null>(null);
  const answer = async (role: RoleKey, body: { answer: string; reason?: string }) => {
    try {
      await apiSend("POST", `/api/intents/${intentId}/roles/${role}/answer`, body);
      setDeclining(null);
      setProblem(null);
      onAnswered();
    } catch (e) {
      setProblem(problemText(e));
    }
  };
  const ends = data.intent.ends ? new Date(data.intent.ends).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" }) : null;
  return (
    <div className="ch-request">
      {data.mine.map((r) => {
        const a = r.answer;
        return (
          <section key={r.role} className="ds-card ch-panel" aria-label={r.label}>
            <h2 style={{ margin: 0 }}>{r.role === "informed" ? t.informed(data.intent.title) : t.requestTitle(data.organiser ?? "The organiser", r.label.toLowerCase(), data.intent.title)}</h2>
            <strong>{t.duty}</strong>
            <p style={{ margin: 0 }}>{r.duty}</p>
            {data.intent.purpose ? <p className="ds-soft" style={{ margin: 0 }}>{data.intent.purpose}</p> : null}
            {ends ? <p className="ds-soft" style={{ margin: 0 }}>{t.until(ends)}</p> : null}
            {a.state === "waiting" || (!data.handed_over && a.state !== "not_asked") ? (
              r.role === "informed" ? (
                a.state === "seen" ? <p role="status">{t.youSaw(day(a.at))}</p> : <Button variant="primary" onClick={() => void answer(r.role, { answer: "seen" })}>{t.gotIt}</Button>
              ) : declining === r.role ? (
                <div className="ch-row">
                  <label className="ch-field">{t.declineWhy}<input type="text" value={reason} maxLength={300} onChange={(e) => setReason(e.target.value)} /></label>
                  <Button variant="primary" disabled={!reason.trim()} onClick={() => void answer(r.role, { answer: "decline", reason })}>{t.sendDecline}</Button>
                  <Button onClick={() => setDeclining(null)}>{t.cancel}</Button>
                </div>
              ) : (
                <div className="ch-row">
                  {a.state === "accepted" ? <p role="status" style={{ margin: 0 }}>{t.youAccepted(day(a.at))}</p> : null}
                  {a.state === "declined" ? <p role="status" style={{ margin: 0 }}>{t.youDeclined(day(a.at))}</p> : null}
                  {a.state !== "accepted" ? <Button variant="primary" onClick={() => void answer(r.role, { answer: "accept" })}>{t.accept(r.label)}</Button> : null}
                  {a.state !== "declined" ? <Button onClick={() => setDeclining(r.role)}>{t.decline}</Button> : null}
                </div>
              )
            ) : data.handed_over ? <p className="ds-muted">{t.handed}</p> : null}
          </section>
        );
      })}
      <section className="ds-card ch-panel" aria-label={t.others}>
        <strong>{t.others}</strong>
        {data.others.length === 0 ? <p className="ds-muted" style={{ margin: 0 }}>{t.first}</p> : data.others.map((r) => (
          <div key={r.role} className="ch-row"><span>{r.label}: <strong>{r.person}</strong></span><Pill tone={tone(r.answer.state)}>{t.answers[r.answer.state] ?? r.answer.state}</Pill></div>
        ))}
      </section>
      {problem ? <p role="alert" className="ds-warn">{problem}</p> : null}
    </div>
  );
}
