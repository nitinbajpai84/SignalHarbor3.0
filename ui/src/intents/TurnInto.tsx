import { useState } from "react";
import { Link } from "react-router-dom";

import { apiSend, ApiError } from "../api/client";
import { Button, Chip } from "../design";
import { turnCopy as t, typeName } from "./pastCopy";
import "./past.css";

/** "Turn this into..." (spec 20 Screens A and B): North's proposal from POST /links/proposal, then POST /links writes the draft
 * (or the backlog item, or the Build hand-off) and both link entries. The panel opens as a right-hand sheet, full screen at 390. */

interface Kind { kind: string; why: string; suggested: boolean; linked: { id: string | null; title: string } | null }
interface Proposal {
  kinds: Kind[]; source: { title: string; type: string; purpose: string; version: number };
  draft: { kind: string; title: string; start_answers: { n: string; answer: unknown; why?: string }[]; people: string[]; areas: string[]; private_item: boolean };
}

const shown = (v: unknown): string => {
  if (Array.isArray(v)) return v.join(", ");
  if (v && typeof v === "object") { const c = v as { value?: unknown; line?: string }; return c.line ?? shown(c.value); }
  return String(v ?? "");
};

export default function TurnInto({ intentId, me }: { intentId: string; me: string }) {
  const [p, setP] = useState<Proposal | null>(null);
  const [error, setError] = useState("");
  const [title, setTitle] = useState("");
  const [people, setPeople] = useState<string[]>([]);
  const [areas, setAreas] = useState<string[]>([]);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<{ kind: string; id: string } | null>(null);

  const load = async (kind?: string) => {
    setError("");
    try {
      const r = await apiSend<Proposal>("POST", `/api/intents/${intentId}/links/proposal`, kind ? { to_kind: kind } : {});
      setP(r); setTitle(r.draft.title);
      if (!kind) { setPeople(r.draft.people.filter((n) => n === me)); setAreas(r.draft.areas); }
    } catch (e) { setError(e instanceof ApiError && e.message ? e.message : t.failed); }
  };
  const create = async () => {
    if (!p || busy) return;
    setBusy(true); setError("");
    try {
      const r = await apiSend<{ target: { kind: string; id: string } }>("POST", `/api/intents/${intentId}/links`, {
        version: p.source.version, to_kind: p.draft.kind, title, carry: { people, areas },
        reason: p.draft.kind === "backlog" ? reason : undefined, note: p.draft.kind === "build" ? reason : undefined,
      });
      setDone(r.target);
    } catch (e) { setError(e instanceof ApiError && e.message ? e.message : t.failed); } finally { setBusy(false); }
  };
  const close = () => { setP(null); setDone(null); setReason(""); };
  const flip = (list: string[], v: string) => (list.includes(v) ? list.filter((x) => x !== v) : [...list, v]);

  if (!p) {
    return (
      <span className="pi-row">
        <Button onClick={() => void load()}>{t.button}</Button>
        {error ? <span role="alert" className="pi-warn">{error}</span> : null}
      </span>
    );
  }
  const kind = p.draft.kind;
  const plain = kind !== "backlog" && kind !== "build";
  const answers = p.draft.start_answers;
  const ready = !!title.trim() && (plain ? areas.length > 0 : kind === "build" || !!reason.trim());
  return (
    <div className="pi-sheet" role="presentation" onClick={close}>
      <aside className="pi-sheet__body" role="dialog" aria-label={t.title} onClick={(e) => e.stopPropagation()}>
        <strong style={{ fontSize: 18 }}>{t.title}</strong>
        <div className="pi-stack" role="group" aria-label={t.title}>
          {p.kinds.map((k) => (
            <div key={k.kind} className="pi-row">
              {k.linked?.id && k.kind !== "backlog" && k.kind !== "build"
                ? <Link className="ds-chip" to={`/centre/intent/${k.linked.id}`}>{typeName[k.kind]} · {t.linked(k.linked.title)}</Link>
                : <Chip tone={k.kind === kind ? "active" : "default"} onClick={() => void load(k.kind)}>{typeName[k.kind] ?? k.kind}{k.suggested ? ` · ${t.suggests}` : ""}</Chip>}
              {k.why ? <span className="ds-muted">{k.why}</span> : null}
            </div>
          ))}
        </div>
        <section className="pi-section"><h3>{t.source}</h3>
          <span>{p.source.title} · {typeName[p.source.type]}</span><span className="ds-muted">{p.source.purpose}</span>
          {p.draft.private_item ? <span className="ds-muted">{t.privateItem}</span> : null}
        </section>
        {done ? (
          <div className="ds-card pi-agent pi-stack" role="status">
            {done.kind === "backlog"
              ? <span>{t.addedBacklog} <Link className="ds-link" to={`/centre/intent/backlog?item=${done.id}`}>{t.seeBacklog}</Link></span>
              : done.kind === "build" ? <span>{t.handed}</span>
                : <span>{t.created} <Link className="ds-link" to={`/centre/intent/new?type=${done.kind}&from=${intentId}&draft=${done.id}`}>{t.openIt}</Link></span>}
            <span><Button onClick={close}>{t.cancel}</Button></span>
          </div>
        ) : (
          <form className="pi-stack" onSubmit={(e) => { e.preventDefault(); void create(); }}>
            <label className="pi-section"><h3>{t.newTitle}</h3>
              <input className="pi-field" type="text" value={title} maxLength={200} onChange={(e) => setTitle(e.target.value)} /></label>
            {!title.trim() ? <span className="pi-warn">{t.noTitle}</span> : null}
            {plain ? (
              <>
                <section className="pi-section"><h3>{t.questions}</h3>
                  {answers.length ? answers.map((a) => (
                    <div key={a.n} className="pi-stack" style={{ gap: 2 }}>
                      <span>{t.question[a.n] ?? a.n}</span><strong>{a.n === "areas" ? p.draft.areas.join(", ") : shown(a.answer)}</strong>
                      <span className="pi-row"><Chip>{t.fromChip(p.source.title)}</Chip><span className="ds-muted">{t.why(a.why ?? "copied from the source")}</span></span>
                    </div>
                  )) : <span className="ds-muted">{t.nothing}</span>}
                  <span className="ds-muted">{t.notFilled}</span>
                </section>
                <section className="pi-section"><h3>{t.people}</h3><span className="ds-muted">{t.peopleNote}</span>
                  {p.draft.people.length ? p.draft.people.map((n) => (
                    <label key={n} className="pi-row"><input type="checkbox" checked={people.includes(n)} onChange={() => setPeople(flip(people, n))} /> {n}</label>
                  )) : <span className="ds-muted">{t.noPeople}</span>}
                </section>
                <section className="pi-section"><h3>{t.areas}</h3>
                  {p.draft.areas.length ? p.draft.areas.map((a) => (
                    <label key={a} className="pi-row"><input type="checkbox" checked={areas.includes(a)} onChange={() => setAreas(flip(areas, a))} /> {a}</label>
                  )) : <span className="pi-warn">{t.noAreas}</span>}
                </section>
                <span className="ds-muted">{t.time}</span>
              </>
            ) : (
              <label className="pi-section"><h3>{kind === "backlog" ? t.reason : t.note}</h3>
                <input className="pi-field" type="text" value={reason} maxLength={500} placeholder={kind === "build" ? t.optional : ""} onChange={(e) => setReason(e.target.value)} />
                {kind === "backlog" && !reason.trim() ? <span className="pi-warn">{t.needReason}</span> : null}
              </label>
            )}
            {error ? <p role="alert" className="df-alert">{error}</p> : null}
            <div className="pi-row">
              <Button type="submit" variant="primary" disabled={!ready || busy}>{t.create(kind)}</Button>
              <Button onClick={close}>{t.cancel}</Button>
            </div>
          </form>
        )}
      </aside>
    </div>
  );
}
