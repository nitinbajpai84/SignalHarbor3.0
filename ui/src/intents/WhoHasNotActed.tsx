import { useEffect, useState } from "react";

import { ApiError, apiGet, apiSend } from "../api/client";
import Panel from "../components/Panel";
import { Button, Chip, DataTable } from "../design";
import { whoCopy as t } from "./yourTurnCopy";

// The organiser's panel on an open intent (spec 45, screen B): names and what they owe, one draft for the ticked people, nothing sent without a click.
interface Who {
  active: boolean; count_stage: string; anonymous: boolean; nudged_at: string | null; cooling: boolean;
  people: { person_id: string; name: string; owes: string; since: string | null }[];
}
interface Draft { id: string; subject: string; body: string; chat: string }

const day = (iso: string): string => new Date(iso).toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" });
const sameDay = (iso: string): boolean => new Date(iso).toDateString() === new Date().toDateString();

export default function WhoHasNotActed({ intentId }: { intentId: string }) {
  const [who, setWho] = useState<Who | null>(null);
  const [failed, setFailed] = useState(false);
  const [ticked, setTicked] = useState<string[]>([]);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let live = true;
    apiGet<Who>(`/api/intents/${intentId}/who-has-not-acted`)
      .then((d) => { if (live) { setWho(d); setTicked((old) => (old.length ? old.filter((i) => d.people.some((p) => p.person_id === i)) : d.people.map((p) => p.person_id))); setFailed(false); } })
      .catch((e: unknown) => { if (live) { setWho(null); setFailed(!(e instanceof ApiError && (e.status === 403 || e.status === 404))); } });
    return () => { live = false; };
  }, [intentId, attempt]);

  if (failed) {
    return <Panel title={t.heading}><p role="alert" className="state state-error">{t.error}</p><button type="button" className="n-btn" onClick={() => setAttempt((a) => a + 1)}>{t.reload}</button></Panel>;
  }
  if (!who || !who.active) return null; // organiser only, and only while the intent is open

  const nudge = async () => {
    setBusy(true);
    setNote(t.drafting);
    try {
      const r = await apiSend<{ message: Draft }>("POST", `/api/intents/${intentId}/nudge/all`, { to: ticked });
      setDraft(r.message);
      setNote(null);
      setAttempt((a) => a + 1);
    } catch (e) {
      setNote(e instanceof ApiError ? e.message : t.error);
    } finally {
      setBusy(false);
    }
  };
  const send = async () => {
    if (!draft) return;
    try {
      await apiSend("POST", `/api/pulse/messages/${draft.id}/send`);
      setNote(t.sent);
    } catch (e) {
      setNote(e instanceof ApiError ? (e.status === 503 ? t.noEmail : e.message) : t.error);
    }
  };
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(draft?.chat ?? "");
      setNote(t.copied);
    } catch {
      setNote(draft?.chat ?? null);
    }
  };
  const rows = who.people.map((p) => ({
    pick: <input type="checkbox" aria-label={t.select(p.name)} checked={ticked.includes(p.person_id)}
      onChange={(e) => setTicked(e.target.checked ? [...ticked, p.person_id] : ticked.filter((x) => x !== p.person_id))} />,
    name: p.name, owes: p.owes, since: p.since ? t.since(day(p.since)) : t.sinceMissing,
  }));
  return (
    <Panel title={t.heading} label="Who has not acted" actions={<span className="n-muted">{who.count_stage}</span>}>
      {who.people.length === 0 ? <p>{t.everyone}</p> : (
        <>
          <DataTable columns={[{ key: "pick", label: "" }, { key: "name", label: t.columns.name }, { key: "owes", label: t.columns.owes }, { key: "since", label: t.columns.since }]} rows={rows} />
          <p style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
            {who.cooling && who.nudged_at
              ? <Chip>{t.nudged(sameDay(who.nudged_at))}</Chip>
              : <Button variant="primary" disabled={busy || ticked.length === 0} onClick={nudge}>{t.nudge(ticked.length)}</Button>}
            {!who.cooling && ticked.length === 0 && <span className="n-muted">{t.tick}</span>}
          </p>
        </>
      )}
      {who.anonymous && <p className="n-muted">{t.anonymous}</p>}
      {draft && (
        <div className="n-who-draft" style={{ display: "grid", gap: 8 }}>
          <strong>{t.draftHeading}</strong>
          <label>{t.subject}<input type="text" value={draft.subject} onChange={(e) => setDraft({ ...draft, subject: e.target.value })} /></label>
          <label>{t.body}<textarea rows={5} value={draft.body} onChange={(e) => setDraft({ ...draft, body: e.target.value })} /></label>
          <p className="n-muted">{t.chat}: {draft.chat}</p>
          <p className="n-muted">{t.edited}</p>
          <p style={{ display: "flex", gap: 12 }}><Button onClick={copy}>{t.copy}</Button><Button onClick={send}>{t.send}</Button></p>
        </div>
      )}
      {note && <p role="status" className="n-muted">{note}</p>}
    </Panel>
  );
}
