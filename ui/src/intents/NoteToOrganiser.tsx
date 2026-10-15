import { useCallback, useEffect, useState } from "react";

import { ApiError, apiGet, apiSend } from "../api/client";
import ScreenState from "../components/ScreenState";
import { Button, SideCard } from "../design";
import { affectedCopy as t } from "./affectedCopy";

interface Req { id: string; state: "open" | "accepted" | "declined" | "withdrawn"; asked_role: string; at: string; role_given: string | null; decline_reason: string | null }
interface Mine { role: "affected" | "observer" | "member" | null; follow: boolean; request: Req | null; replies: { id: string; by: string | null; text: string }[] }
const READ_ONLY = "You can read this intent but not change it."; // the server's sentence for a refused write (access.py)
const NOTE_MAX = 500;
const REASON_MAX = 300;
const day = (iso: string) => new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short" });

/** The "Your part" panel for an affected person or an observer (spec 47, screens C, F, G): follow, a note to the organiser (affected people
 * only), and ask to join. An observer sees the role note and follow, and nothing that writes to the content. */
export default function NoteToOrganiser({ intentId, organiser }: { intentId: string; organiser?: string }) {
  const base = `/api/intents/${encodeURIComponent(intentId)}`;
  const [mine, setMine] = useState<Mine | null | "failed">(null);
  const [text, setText] = useState("");
  const [signed, setSigned] = useState(true);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState("");
  const [asking, setAsking] = useState(false);
  const [role, setRole] = useState("participant");
  const [reason, setReason] = useState("");
  const who = organiser || t.organiserFallback;

  const [none, setNone] = useState(false);
  const load = useCallback(() => apiGet<{ mine: Mine; state?: string }>(`${base}/notes`).then((r) => (r.state === "closed" || r.state === "cancelled" ? setNone(true) : setMine(r.mine)),
    (e) => (e instanceof ApiError && (e.status === 403 || e.status === 404) ? setNone(true) : setMine("failed"))), [base]);
  useEffect(() => { void load(); }, [load]);

  if (none || (mine && mine !== "failed" && mine.role === null)) return null; // no part here: the organiser, a participant, a named owner, or a closed intent (W2F2)
  if (mine === null) return <ScreenState state="loading" />;
  if (mine === "failed") return <ScreenState state="error" message={t.loadError} onRetry={load} />;
  const observer = mine.role === "observer";
  const mayNote = mine.role === "affected"; // the server takes notes from affected people only (access.py NOTE)
  const act = async (fn: () => Promise<unknown>, done?: () => void) => {
    setError("");
    try { await fn(); done?.(); await load(); } catch (e) { setError(e instanceof ApiError && e.status === 403 ? READ_ONLY : e instanceof Error && e.message ? e.message : t.saveError); }
  };
  const req = mine.request;

  return (
    <SideCard title={t.yourPart}>
      {observer && <p className="n-muted">{t.observerNote}</p>}
      <label style={{ display: "block", padding: "8px 0" }}>
        <input type="checkbox" checked={mine.follow} onChange={(e) => act(() => apiSend("POST", `${base}/follow`, { follow: e.target.checked }))} /> {t.follow}
        <span className="n-muted" style={{ display: "block" }}>{t.followHelp}</span>
      </label>

      {mayNote && (
        <section aria-label={t.noteTitle}>
          <strong>{t.noteTitle}</strong>
          <textarea value={text} maxLength={NOTE_MAX} rows={4} style={{ width: "100%", boxSizing: "border-box" }} aria-label={t.noteTitle}
            placeholder={t.notePlaceholder(who)} onChange={(e) => { setText(e.target.value); setSent(false); }} />
          <label style={{ display: "block", padding: "6px 0" }}>
            <input type="checkbox" checked={!signed} onChange={(e) => setSigned(!e.target.checked)} /> {t.sendWithoutName}
          </label>
          <Button variant="primary" disabled={!text.trim()} onClick={() => act(() => apiSend("POST", `${base}/notes`, { text, signed }), () => { setText(""); setSent(true); })}>{t.sendNote}</Button>
          {sent && <p role="status">{t.sent(who)}</p>}
          {mine.replies.map((r) => <p key={r.id}><strong>{t.replyFrom(r.by ?? who)}</strong>: {r.text}</p>)}
        </section>
      )}

      {!observer && <section style={{ paddingTop: 12 }}>
        {req?.state === "open" ? (
          <>
            <p>{t.asked(day(req.at))}</p>
            <Button onClick={() => act(() => apiSend("POST", `${base}/join-requests/${req.id}/withdraw`))}>{t.withdraw}</Button>
          </>
        ) : req?.state === "declined" ? (
          <p>{t.declined(req.decline_reason ?? "")}</p>
        ) : req?.state === "accepted" ? (
          <p>{t.accepted(req.role_given ?? "participant")}</p>
        ) : (
          <Button onClick={() => { setAsking(true); setRole("participant"); }}>{t.askToJoin}</Button>
        )}
      </section>}

      {asking && (
        <div role="dialog" aria-modal="true" aria-label={t.askToJoin} className="ds-card"
          style={{ position: "fixed", inset: 0, margin: "auto", width: "min(480px, 100%)", height: "fit-content", padding: 20, zIndex: 50 }}>
          {!observer && (
            <fieldset style={{ border: 0, padding: 0 }}>
              <label style={{ display: "block", padding: "6px 0" }}><input type="radio" name="asked-role" checked={role === "participant"} onChange={() => setRole("participant")} /> {t.takePart}</label>
              <label style={{ display: "block", padding: "6px 0" }}><input type="radio" name="asked-role" checked={role === "observer"} onChange={() => setRole("observer")} /> {t.readAlong}</label>
            </fieldset>
          )}
          <label htmlFor="join-reason">{t.reasonLabel}</label>
          <textarea id="join-reason" value={reason} maxLength={REASON_MAX} rows={3} style={{ width: "100%", boxSizing: "border-box" }} onChange={(e) => setReason(e.target.value)} />
          <Button variant="primary" disabled={!reason.trim()}
            onClick={() => act(() => apiSend("POST", `${base}/join-requests`, { asked_role: role, reason }), () => { setAsking(false); setReason(""); })}>{t.sendRequest}</Button>{" "}
          <Button onClick={() => setAsking(false)}>{t.cancel}</Button>
        </div>
      )}
      {error && <p role="alert" className="state state-error">{error}</p>}
    </SideCard>
  );
}
