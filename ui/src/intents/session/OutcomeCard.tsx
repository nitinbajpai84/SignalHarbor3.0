import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import Panel from "../../components/Panel";
import ScreenState from "../../components/ScreenState";
import { Button, Chip } from "../../design";
import { converge, figure, useConverge, when, type Chosen, type Loaded, type View } from "./convergeApi";
import { t } from "./convergeCopy";
import "./converge.css";

const sourceLabel = (s: string) => (s === "north_suggestion" ? t.northSuggestion : s);
const leaders = (v: View) => {
  const top = Math.max(0, ...(v.candidates ?? []).map((c) => c.backed));
  return (v.candidates ?? []).filter((c) => top > 0 && c.backed === top);
};

interface Take { text: string; source: string }

function Card({ v, c, l, intentId, back }: { v: View; c: Chosen; l: Loaded; intentId: string; back?: () => void }) {
  const nav = useNavigate();
  const editable = v.viewer.organiser && !v.outcome.confirmed;
  const [idea, setIdea] = useState(c.idea);
  const [why, setWhy] = useState(c.why);
  const [takes, setTakes] = useState<Take[]>(c.what_it_takes);
  const [swap, setSwap] = useState<string | null>(null);
  const [swapWhy, setSwapWhy] = useState("");
  const [removing, setRemoving] = useState<{ ref: string; reason: string } | null>(null);
  const [all, setAll] = useState(false);
  const lead = leaders(v);
  const most = lead.some((x) => x.ref === c.ref);
  const dirty = idea !== c.idea || why !== c.why || JSON.stringify(takes) !== JSON.stringify(c.what_it_takes);
  const miss = !idea.trim() ? t.noIdea : !most && !c.overridden_reason ? t.whyOverride : !why.trim() ? t.addReason
    : !takes.some((x) => x.text.trim()) ? t.takesEmpty : "";
  const kept = v.outcome.ideas_kept;
  const runners = kept.filter((k) => k.runner_up);
  const rest = kept.filter((k) => !k.runner_up);
  const rounds = Object.entries(c.by_rounds ?? {});
  const save = () => l.run(() => converge.edit(intentId, { idea, why, what_it_takes: takes }));
  const confirm = async () => {
    if (dirty && !(await save())) return;
    if (await l.run(() => converge.confirm(intentId))) nav(`/centre/intent/${intentId}/close`);
  };
  return (
    <div className="cv-out__grid">
      <div className="cv-card">
        <Panel title={c.idea ? undefined : t.idea}
          actions={c.confirmed_by ? <Chip tone="active">{t.confirmedBy(c.confirmed_by.name, when(c.confirmed_at, v.tz, false))}</Chip>
            : <Chip>{c.drafted_by ? (c.fallback ? t.draftCounted : t.draftBy) : t.edited}</Chip>}>
          <div className="cv-field">
            <label htmlFor="cv-idea">{t.idea}</label>
            {editable ? <textarea id="cv-idea" rows={4} value={idea} onChange={(e) => setIdea(e.target.value)} /> : <p>{c.idea || t.noIdea}</p>}
          </div>
          {editable && v.candidates && v.candidates.length > 1 && (
            <details className="cv-field cv-pick">
              <summary>{t.differentIdea}</summary>
              {v.candidates.map((x) => (
                <label key={x.ref} className="cv-radio">
                  <input type="radio" name="cv-swap" checked={swap === x.ref} onChange={() => setSwap(x.ref)} />
                  {x.text} ({t.backedCount(x.backed)})
                </label>
              ))}
              {swap && swap !== c.ref && (
                <>
                  {!lead.some((x) => x.ref === swap) && (
                    <>
                      <label htmlFor="cv-swapwhy">{t.whyOverride}</label>
                      <input id="cv-swapwhy" type="text" value={swapWhy} onChange={(e) => setSwapWhy(e.target.value)} />
                    </>
                  )}
                  <Button disabled={l.busy} onClick={() => l.run(() => converge.edit(intentId, { ref: swap, overridden_reason: swapWhy }))}>{t.differentIdea}</Button>
                </>
              )}
            </details>
          )}
          <div className="cv-field">
            <label htmlFor="cv-why">{t.why}</label>
            {editable ? <textarea id="cv-why" rows={4} value={why} placeholder={t.addReason} onChange={(e) => setWhy(e.target.value)} /> : (
              (c.why_sources.length ? c.why_sources : c.why ? [{ text: c.why, source: "" }] : []).map((s, i) => (
                <p key={i} className="cv-sentence"><span>{s.text}</span>{s.source && <span className="cv-source">{s.source}</span>}</p>
              ))
            )}
            {editable && c.why_sources.length > 0 && (
              <p className="cv-sentence">{c.why_sources.map((s, i) => <span key={i} className="cv-source">{s.source}</span>)}</p>
            )}
            {c.overridden_reason && <p className="ds-muted">{c.overridden_reason}</p>}
          </div>
          <div className="cv-field">
            <strong>{t.takes}</strong>
            {takes.length === 0 && !editable && <p className="ds-muted">{t.takesEmpty}</p>}
            <ul className="cv-takes">
              {takes.map((x, i) => (
                <li key={i}>
                  {editable ? <input type="text" aria-label={t.takes} value={x.text} onChange={(e) => setTakes(takes.map((y, j) => (j === i ? { ...y, text: e.target.value } : y)))} /> : <span>{x.text}</span>}
                  <span className="cv-source">{sourceLabel(x.source)}</span>
                  {editable && <Button onClick={() => setTakes(takes.filter((_, j) => j !== i))}>{t.remove}</Button>}
                </li>
              ))}
            </ul>
            {editable && <Button onClick={() => setTakes([...takes, { text: "", source: "Added by the organiser" }])}>{t.addLine}</Button>}
            {editable && takes.length === 0 && <p className="ds-muted">{t.takesEmpty}</p>}
          </div>
          <div className="cv-field">
            <strong>{t.proposedBy}</strong>
            <p>
              {c.proposed_by.length ? c.proposed_by.map((p) => p.name).join(", ") : t.anonymousOne}
              {c.proposed_by.length > 0 && c.proposed_unnamed > 0 ? ` ${t.andUnnamed(c.proposed_unnamed)}` : ""}
            </p>
          </div>
          <div className="cv-field">
            <strong>{t.backedBy}</strong>
            <p>
              {c.backed_of ? <Chip>{t.backedOf(c.backed, c.backed_of)}</Chip> : t.noCount}
              {rounds.length > 1 && rounds.map(([k, n]) => <Chip key={k}>{`Round ${k.replace("round", "")}: ${n}`}</Chip>)}
            </p>
          </div>
        </Panel>
        <Panel title={t.runnersUp}>
          {kept.length === 0 ? <p className="ds-muted">{t.noOthers}</p> : (
            <ul className="cv-list">
              {runners.map((k) => (
                <li key={k.ref} className="cv-row">
                  <div className="cv-row__main"><strong>{k.text}</strong><span className="cv-chip-line"><Chip>{t.backedCount(k.backed.round2 ?? k.backed.round1)}</Chip></span></div>
                  {editable && <Button onClick={() => setRemoving({ ref: k.ref, reason: "" })}>{t.removeRunner}</Button>}
                  {removing?.ref === k.ref && (
                    <div className="cv-dialog" style={{ flex: "1 1 100%" }}>
                      <label htmlFor="cv-rm">{t.removeWhy}</label>
                      <input id="cv-rm" type="text" value={removing.reason} onChange={(e) => setRemoving({ ref: k.ref, reason: e.target.value })} />
                      <Button disabled={l.busy || !removing.reason.trim()} onClick={async () => { if (await l.run(() => converge.edit(intentId, { remove_runner_up: removing }))) setRemoving(null); }}>{t.removeRunner}</Button>
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )}
          {rest.length > 0 && <Button onClick={() => setAll(!all)} aria-expanded={all}>{t.showAll(rest.length)}</Button>}
          {all && <ul className="cv-list">{rest.map((k) => <li key={k.ref} className="cv-row"><div className="cv-row__main"><strong>{k.text}</strong><span className="cv-chip-line"><Chip>{t.backedCount(k.backed.round2 ?? k.backed.round1)}</Chip></span></div></li>)}</ul>}
        </Panel>
        {editable && (
          <div className="cv-confirm">
            <Button variant="primary" disabled={l.busy || !!miss} onClick={confirm}>{t.confirmOutcome}</Button>
            {miss && <span className="ds-muted">{miss}</span>}
            {dirty && <Button disabled={l.busy} onClick={save}>{t.save}</Button>}
            {back && <Button onClick={back}>{t.backToCount}</Button>}
          </div>
        )}
      </div>
      {v.numbers && (
        <Panel title={t.numbers}>
          <dl className="cv-nums">
            <dt>{t.nIdeas}</dt><dd>{figure(v.numbers.ideas_added)}</dd>
            <dt>{t.nGroups}</dt><dd>{figure(v.numbers.groups)}</dd>
            <dt>{t.nBacks}</dt><dd>{figure(v.numbers.backs_cast)}</dd>
            <dt>{t.nPeople}</dt><dd>{figure(v.numbers.people_backed)}</dd>
            <dt>{t.nRounds}</dt><dd>{figure(v.numbers.rounds_run)}</dd>
            <dt>{t.nMinutes}</dt><dd>{figure(v.numbers.minutes_to_confirm)}</dd>
          </dl>
        </Panel>
      )}
    </div>
  );
}

function Undrafted({ v, l, intentId, back }: { v: View; l: Loaded; intentId: string; back?: () => void }) {
  const closed = v.converge.state === "round_1_closed" || v.converge.state === "round_2_closed";
  const lead = leaders(v);
  return (
    <Panel title={t.idea}>
      <p>{t.notDrafted}</p>
      {v.viewer.organiser && closed && (lead.length > 1 ? (
        <>
          <p>{t.tiedAtTop}</p>
          {lead.map((x) => <Button key={x.ref} disabled={l.busy} onClick={() => l.run(() => converge.draft(intentId, x.ref))}>{`${t.draftWith}: ${x.text.slice(0, 50)}`}</Button>)}
        </>
      ) : <Button variant="primary" disabled={l.busy} onClick={() => l.run(() => converge.draft(intentId))}>{t.draftIt}</Button>)}
      {back && <Button onClick={back}>{t.backToCount}</Button>}
    </Panel>
  );
}

/** Screen B of spec 37 on a loaded view. The late-thought panel sits under it once the outcome is confirmed. */
export function OutcomeBody({ l, intentId, back }: { l: Loaded; intentId: string; back?: () => void }) {
  const v = l.view;
  if (l.failed) return <ScreenState state="error" message={t.failed} onRetry={l.reload} />;
  if (!v) return <ScreenState state="loading" message={t.loading} />;
  const c = v.outcome.chosen;
  return (
    <div className="cv-out ic-phone">
      {l.notice && <p role="alert" className="state state-error">{l.notice}</p>}
      {c ? <Card key={JSON.stringify([c.ref, c.idea, c.why, c.what_it_takes])} v={v} c={c} l={l} intentId={intentId} back={back} />
        : <Undrafted v={v} l={l} intentId={intentId} back={back} />}
      {v.late && <LateBody l={l} intentId={intentId} />}
    </div>
  );
}

/** The outcome card on its own, for a page that mounts only this. */
export function OutcomeCard({ intentId }: { intentId: string }) {
  const l = useConverge(intentId);
  return <OutcomeBody l={l} intentId={intentId} />;
}

// ---- Screen C: What next, a panel for B09's close view -------------------------------------------------------------------------------

export interface NextChoice { kind: string; reason: string; answers: Record<string, Record<string, string | string[]>>; review_date: string | null }
const KIND_ORDER = ["initiative", "problem", "decision", "backlog", "handled", "nothing"];
const show = (x: string | string[]) => (Array.isArray(x) ? x.join(", ") : x);

/**
 * The first row of the Next list for a Brainstorm (spec 37 screen C). B09 mounts it as <WhatNext intentId={id} onChange={...} /> and writes the
 * choice it reports (kind, reason, edited start answers, review date) through PUT /api/intents/<id>/closure. Nothing is written here.
 */
export function WhatNext({ intentId, onChange, readOnly = false }: { intentId: string; onChange?: (c: NextChoice) => void; readOnly?: boolean }) {
  const l = useConverge(intentId);
  const v = l.view;
  const [kind, setKind] = useState("");
  const [reason, setReason] = useState("");
  const [answers, setAnswers] = useState<NextChoice["answers"]>({});
  const [review, setReview] = useState("");
  useEffect(() => { onChange?.({ kind, reason, answers, review_date: review || null }); }, [kind, reason, answers, review]); // eslint-disable-line react-hooks/exhaustive-deps
  if (l.failed) return <ScreenState state="error" message={t.failed} onRetry={l.reload} />;
  if (!v) return <ScreenState state="loading" message={t.loading} />;
  if (!v.outcome.chosen) return <Panel title={t.whatNext}><p className="ds-muted">{t.noOutcome}</p></Panel>;
  const qs = v.prefill?.questions ?? [];
  const bl = v.backlog_preview;
  const val = (q: string, k: string, base: string | string[]) => answers[q]?.[k] ?? base;
  const edit = (q: string, k: string, x: string) => setAnswers({ ...answers, [q]: { ...answers[q], [k]: x } });
  return (
    <Panel title={t.whatNext} className="cv-next">
      <div role="radiogroup" aria-label={t.whatNext}>
        {KIND_ORDER.filter((k) => v.next_kinds.includes(k)).map((k) => (
          <label key={k} className="cv-radio">
            <input type="radio" name="cv-next" value={k} checked={kind === k} disabled={readOnly} onChange={() => setKind(k)} />
            {t.kinds[k]}
          </label>
        ))}
      </div>
      {!kind && <p className="ds-muted">{t.sayNext}</p>}
      {kind === "initiative" && (
        <div className="cv-field">
          {qs.filter((q) => q.from_brainstorm).map((q) => (
            <div key={q.id} className="cv-field">
              <strong>{q.lead} <Chip>{t.fromBrainstorm}</Chip></strong>
              {Object.entries(q.answers).filter(([, x]) => (Array.isArray(x) ? x.length : x)).map(([k, x]) => (
                <input key={k} type="text" aria-label={`${q.lead} (${k})`} value={show(val(q.id, k, x))} disabled={readOnly} onChange={(e) => edit(q.id, k, e.target.value)} />
              ))}
              {q.id === "i2" && <p className="ds-muted">{t.suggested}</p>}
            </div>
          ))}
          <strong>{t.willBeAsked}</strong>
          <ul>{qs.filter((q) => !q.from_brainstorm).map((q) => <li key={q.id}>{q.lead}</li>)}</ul>
        </div>
      )}
      {kind === "backlog" && bl && (
        <div className="cv-field">
          <strong>{t.backlogItem}</strong>
          <p>{bl.title}</p>
          <p className="ds-muted">{bl.why}</p>
          <p>{t.raisedBy}: {bl.raised_by === "unnamed" ? "unnamed" : bl.raised_by}</p>
          {bl.also_considered.length > 0 && <p>{t.alsoConsidered}: {bl.also_considered.join("; ")}</p>}
          <label htmlFor="cv-review">{t.reviewDate}</label>
          <input id="cv-review" type="date" value={review} disabled={readOnly} onChange={(e) => setReview(e.target.value)} />
        </div>
      )}
      {kind && (
        <div className="cv-field">
          <label htmlFor="cv-reason">{t.reason}</label>
          <input id="cv-reason" type="text" value={reason} placeholder={t.reasonNeeded} disabled={readOnly} onChange={(e) => setReason(e.target.value)} />
          {!reason.trim() && <span className="ds-muted">{t.reasonNeeded}</span>}
        </div>
      )}
    </Panel>
  );
}

// ---- Screen D: late thoughts ------------------------------------------------------------------------------------------------------------

function LateBody({ l, intentId }: { l: Loaded; intentId: string }) {
  const v = l.view;
  const [text, setText] = useState("");
  const [anon, setAnon] = useState(false);
  const [about, setAbout] = useState("");
  const late = v?.late;
  if (!v || !late) return null;
  const forced = late.names === "anonymous" ? true : late.names === "named" ? false : anon;
  const add = async () => {
    if (await l.run(() => converge.late(intentId, { text, about: about || late.about[0]?.ref || "", anonymous: forced }))) setText("");
  };
  return (
    <Panel title={t.lateTitle} className="cv-late">
      <p>{late.frozen_at || !late.open ? t.frozenLine : t.window(when(late.closes_at, v.tz))}</p>
      {late.frozen_at && <Chip>{t.frozenChip(when(late.frozen_at, v.tz, false))}</Chip>}
      {late.can_add && (
        <>
          <textarea rows={3} maxLength={late.limit} value={text} placeholder={t.lateHint} aria-label={t.lateField} onChange={(e) => setText(e.target.value)} />
          <span className="ds-muted">{t.count(text.length, late.limit)}</span>
          {late.names === "choice" && (
            <div role="group" aria-label={t.byName}>
              <Chip tone={!anon ? "active" : "default"} onClick={() => setAnon(false)}>{t.byName}</Chip>
              <Chip tone={anon ? "active" : "default"} onClick={() => setAnon(true)}>{t.anonymous}</Chip>
            </div>
          )}
          <label htmlFor="cv-about">{t.about}</label>
          <select id="cv-about" value={about || late.about[0]?.ref} onChange={(e) => setAbout(e.target.value)}>
            {late.about.map((a) => <option key={a.ref} value={a.ref}>{a.text}</option>)}
          </select>
          <Button variant="primary" disabled={l.busy || !text.trim()} onClick={add}>{t.addThought}</Button>
        </>
      )}
      {late.thoughts.length === 0 ? <p className="ds-muted">{t.noLate}</p> : (
        <ul className="cv-late__list">
          {late.thoughts.map((x, i) => (
            <li key={i}>
              <p>{x.text}</p>
              <span className="ds-muted">{[x.anonymous ? t.anonymous : x.name, x.about, when(x.at, v.tz)].filter(Boolean).join(" · ")}</span>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}

/** Screen D on its own, for B09's close view (during closing) and the closed intent page. */
export function LateThoughts({ intentId }: { intentId: string }) {
  const l = useConverge(intentId);
  return l.view?.late ? <LateBody l={l} intentId={intentId} /> : null;
}
