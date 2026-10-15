import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { ApiError, apiGet, apiSend } from "../../api/client";
import ScreenState from "../../components/ScreenState";
import { Button, Chip, SideCard } from "../../design";
import type { StartProps } from "../IntentNew";
import { LinkButton } from "../views/ProblemTriage";
import { BITES, problemStartCopy as t } from "../problemCopy";
import ProblemSteer from "./ProblemSteer";

// The Problem's five start questions (spec 41, screen A). One question at a time, a read-back after each answer, a review card, then the reporter's one press.

interface Item { id: string; name: string; group: string }
interface Person { id: string; name: string; team: string | null; can_own?: boolean }
interface OwnerChip { source: string; name: string; label: string }
interface Options {
  people: Person[]; areas: string[]; catalogue: Item[]; chips: OwnerChip[]; currency?: string | null;
  prefill: { what?: string | null; about?: string | null; owner_source?: string | null; origin?: string | null; alert?: string; from?: string; item?: string; alert_missing?: boolean };
}
interface Answers {
  what: string; saw: string; about: { kind: string; id: string | null; name: string | null } | null; bites: { kind: string; count: string; amount: string } | null;
  owner: { source: string; name: string } | { unknown: true } | null; areas: string[]; affected: string[]; affected_may_read: boolean;
}
const BLANK: Answers = { what: "", saw: "", about: null, bites: null, owner: null, areas: [], affected: [], affected_may_read: false };

const STYLE = `.ps-grid{display:grid;grid-template-columns:2fr 1fr;gap:24px}.ps-bar{display:none}
@media (max-width:899px){.ps-grid{grid-template-columns:1fr}.ps-side{display:none}.ps-bar{display:block}.ps-sheet .ps-side{display:block}}`;

function North({ children }: { children: React.ReactNode }) {
  return <div className="ds-card" style={{ padding: 12, margin: "0 0 12px" }}><strong>{t.north}</strong> <span>{children}</span></div>;
}

function endDate(days: number): string { // working days (Monday to Friday) from today, in the browser's own time zone
  const d = new Date();
  for (let n = days; n > 0;) { d.setDate(d.getDate() + 1); if (d.getDay() % 6) n -= 1; }
  return d.toLocaleDateString("en-GB", { day: "numeric", month: "short" });
}

function Pick<T extends { key: string }>({ items, label, onPick, render, empty }: { items: T[]; label: string; onPick: (x: T) => void; render: (x: T) => React.ReactNode; empty: string }) {
  const [q, setQ] = useState("");
  const shown = items.filter((x) => JSON.stringify(x).toLowerCase().includes(q.toLowerCase()));
  return (
    <div>
      <input type="text" aria-label={label} placeholder={label} value={q} onChange={(e) => setQ(e.target.value)} style={{ width: "100%", minHeight: 44, boxSizing: "border-box" }} />
      {items.length === 0 ? <p className="n-muted">{empty}</p> : shown.length === 0 ? <p className="n-muted">{t.q2.none}</p> : (
        <ul role="listbox" aria-label={label} style={{ listStyle: "none", padding: 0, margin: "8px 0", maxHeight: 260, overflow: "auto" }}>
          {shown.map((x) => (
            <li key={x.key}><button type="button" role="option" aria-selected={false} className="ds-card" style={{ width: "100%", textAlign: "left", padding: 10, margin: "4px 0", minHeight: 44, cursor: "pointer" }} onClick={() => onPick(x)}>{render(x)}</button></li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function ProblemStart({ draftId, catalogue }: StartProps) {
  const [params] = useSearchParams();
  const nav = useNavigate();
  const [opts, setOpts] = useState<Options | null | "failed">(null);
  const [a, setA] = useState<Answers>(BLANK);
  const [step, setStep] = useState(0);
  const [readback, setReadback] = useState(false);
  const [origin, setOrigin] = useState<string | null>(null);
  const [links, setLinks] = useState<{ alert?: string; from?: string; item?: string }>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [sheet, setSheet] = useState(false);
  const [other, setOther] = useState(false);
  const days = catalogue.time_box_days ?? 5;

  const load = useCallback(() => {
    setOpts(null);
    const q = new URLSearchParams();
    for (const k of ["alert", "item", "from"]) { const v = params.get(k); if (v) q.set(k, v); }
    Promise.all([
      apiGet<Options>(`/api/intents/problem/start?${q.toString()}`),
      apiGet<{ start_answers?: Partial<Answers> & { step?: number } }>(`/api/intents/${draftId}/problem`).catch(() => null),
    ]).then(([o, draft]) => {
      setOpts(o);
      const saved = draft?.start_answers;
      if (saved && saved.what) { setA({ ...BLANK, ...saved } as Answers); setStep(Math.min(saved.step ?? 0, 5)); return; }
      const p = o.prefill;
      const hit = p.about ? o.catalogue.find((c) => c.id === p.about) : undefined;
      const chip = p.owner_source ? o.chips.find((c) => c.source === p.owner_source) : undefined;
      setA({ ...BLANK, what: p.what ?? "", about: hit ? { kind: hit.group === "Measures" ? "measure" : "process", id: hit.id, name: hit.name } : null,
        owner: chip ? { source: chip.source, name: chip.name } : null });
      setOrigin(p.alert_missing ? t.alertMissing : p.origin ?? null);
      setLinks({ alert: p.alert, from: p.from, item: p.item });
    }, () => setOpts("failed"));
  }, [draftId, params]);
  useEffect(load, [load]);

  const aboutId = a.about?.id;
  useEffect(() => { // the owner chips follow the pick
    if (!aboutId || opts === null || opts === "failed") return;
    apiGet<Options>(`/api/intents/problem/start?about=${encodeURIComponent(aboutId)}`).then((o) => setOpts((cur) => (cur && cur !== "failed" ? { ...cur, chips: o.chips } : cur))).catch(() => undefined);
  }, [aboutId]); // eslint-disable-line react-hooks/exhaustive-deps

  const body = useMemo(() => ({
    what: a.what, saw: a.saw, about: a.about ?? { kind: "unknown" }, owner: a.owner && "source" in a.owner ? a.owner : null, areas: a.areas, affected: a.affected, affected_may_read: a.affected_may_read,
    bites: a.bites ? { kind: a.bites.kind, count: a.bites.count === "" ? null : Number(a.bites.count), amount: a.bites.amount === "" ? null : Number(a.bites.amount),
                       unit: a.bites.kind === "cost_money" ? (opts && opts !== "failed" ? opts.currency ?? null : null) : null } : null, ...links,
  }), [a, links, opts]);

  const save = async (to: number, open = false) => {
    setError(""); setBusy(true);
    try {
      await apiSend("POST", `/api/intents/${draftId}/problem/start`, { ...body, open, step: to });
      if (open) { nav(`/centre/intent/${draftId}`); return; }
      return true;
    } catch (e) { setError(e instanceof ApiError && e.status === 422 ? e.message : t.failed); }
    finally { setBusy(false); }
  };

  if (opts === null) return <ScreenState state="loading" />;
  if (opts === "failed") return <ScreenState state="error" message={t.loadFailed} onRetry={load} />;

  const valid = [a.what.trim() !== "" && a.saw.trim() !== "", a.about !== null, a.bites !== null, a.owner !== null, a.areas.length > 0 && a.affected.length > 0][step];
  const missing = !a.what.trim() || !a.saw.trim() ? "what is wrong" : !a.bites ? "how hard it bites" : !a.areas.length || !a.affected.length ? "areas and who feels it" : "";
  const aboutText = a.about?.name ?? t.review.notSure;
  const ownerText = !a.owner ? "" : "source" in a.owner ? a.owner.name : "I do not know";
  const read = [
    a.what, a.about?.name ?? t.review.notSure,
    a.bites ? `${BITES[a.bites.kind]}${a.bites.count ? `, ${a.bites.count} times or items` : ""}` : "", ownerText, `${a.areas.join(", ")}; felt by ${a.affected.join(", ")}`,
  ];
  const unit = opts.currency;
  const set = (p: Partial<Answers>) => setA((x) => ({ ...x, ...p }));
  const next = async () => { if (await save(step)) setReadback(true); };
  const yes = async () => { const to = step + 1; setReadback(false); setStep(to); setOther(false); await save(to); };

  const catItems = opts.catalogue.map((c) => ({ ...c, key: c.id }));
  const words = new Set(a.what.toLowerCase().split(/\W+/).filter((w) => w.length > 3));
  const suggested = (c: Item) => c.name.toLowerCase().split(/\W+/).some((w) => words.has(w));
  const peopleItems = opts.people.map((p) => ({ ...p, key: p.id }));

  const summary = (
    <SideCard title={t.summaryTitle}>
      <dl style={{ margin: 0 }}>
        {[["What is wrong", a.what], ["About", a.about ? aboutText : step > 1 ? t.review.notSure : ""], ["How hard", a.bites ? BITES[a.bites.kind] : ""], ["Proposed owner", ownerText],
          ["Areas", a.areas.join(", ")], ["Who feels it", a.affected.join(", ")]].map(([k, v]) => (
          <div key={k} style={{ marginBottom: 8 }}><dt className="n-muted">{k}</dt><dd style={{ margin: 0 }}>{v || "-"}</dd></div>
        ))}
      </dl>
    </SideCard>
  );

  const question = (
    <>
      {step === 0 && (
        <>
          {readback && <ProblemSteer draftId={draftId} what={a.what} saw={a.saw} />}
          <North>{t.q1.lead}</North>
          <label>{t.q1.line}<input type="text" aria-label={t.q1.line} maxLength={140} placeholder={t.q1.placeholder} value={a.what} onChange={(e) => set({ what: e.target.value })} style={{ display: "block", width: "100%", minHeight: 44, boxSizing: "border-box" }} /></label>
          <label style={{ display: "block", marginTop: 12 }}>{t.q1.saw}<textarea aria-label={t.q1.saw} maxLength={600} rows={4} placeholder={t.q1.sawPlaceholder} value={a.saw} onChange={(e) => set({ saw: e.target.value })} style={{ display: "block", width: "100%", boxSizing: "border-box" }} /></label>
        </>
      )}
      {step === 1 && (
        <>
          <North>{t.q2.lead} <span className="n-muted">{t.q2.why}</span></North>
          {a.about && <p>{a.about.kind === "unknown" ? <strong>{t.q2.notSure}</strong> : <><Chip>{a.about.kind === "measure" ? t.q2.measures : t.q2.processes}</Chip> <strong>{a.about.name}</strong></>} <Button onClick={() => { set({ about: null }); setReadback(false); }}>{t.q2.remove}</Button></p>}
          {!a.about && <>
            <Pick items={[...catItems].sort((x, y) => Number(suggested(y)) - Number(suggested(x)))} label={t.q2.search} empty={t.q2.empty}
              onPick={(c) => set({ about: { kind: c.group === "Measures" ? "measure" : "process", id: c.id, name: c.name } })}
              render={(c) => <><strong>{c.name}</strong> <Chip>{c.group === "Measures" ? t.q2.measures : t.q2.processes}</Chip> {suggested(c) && <Chip tone="active">{t.suggested}</Chip>}</>} />
            <Button onClick={() => { set({ about: { kind: "unknown", id: null, name: null } }); setReadback(true); }}>{t.q2.notSure}</Button>
          </>}
        </>
      )}
      {step === 2 && (
        <>
          <North>{t.q3.lead}</North>
          <div role="radiogroup" aria-label="How hard">
            {Object.entries(BITES).map(([k, label]) => (
              <label key={k} style={{ display: "block", minHeight: 44 }}><input type="radio" name="bites" checked={a.bites?.kind === k} onChange={() => set({ bites: { kind: k, count: a.bites?.count ?? "", amount: k === "cost_money" ? a.bites?.amount ?? "" : "" } })} /> {label}</label>
            ))}
          </div>
          {a.bites && <label style={{ display: "block", marginTop: 8 }}>{t.q3.count}<input type="number" min={0} aria-label={t.q3.count} value={a.bites.count} onChange={(e) => set({ bites: { ...a.bites!, count: e.target.value } })} style={{ display: "block", minHeight: 44 }} /></label>}
          {a.bites?.kind === "cost_money" && (unit
            ? <label style={{ display: "block", marginTop: 8 }}>{t.q3.amount(unit)}<input type="number" min={0} aria-label={t.q3.amount(unit)} value={a.bites.amount} onChange={(e) => set({ bites: { ...a.bites!, amount: e.target.value } })} style={{ display: "block", minHeight: 44 }} /></label>
            : <p className="n-muted">{t.q3.noCurrency}</p>)}
        </>
      )}
      {step === 3 && (
        <>
          <North>{t.q4.lead}</North>
          {opts.chips.length > 0 && <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            {opts.chips.map((c) => (
              <div key={c.source}><Chip tone={a.owner && "source" in a.owner && a.owner.source === c.source && a.owner.name === c.name ? "active" : "default"}
                onClick={() => { set({ owner: { source: c.source, name: c.name } }); setOther(false); }}>{`${t.q4.chipLabel[c.source]}: ${c.name}`}</Chip><small className="n-muted" style={{ display: "block" }}>{t.q4.suggestedFrom[c.source]}</small></div>
            ))}
          </div>}
          <p style={{ marginTop: 12 }}><Button onClick={() => setOther(!other)} aria-expanded={other}>{t.q4.pick}</Button> <Button onClick={() => { set({ owner: { unknown: true } }); setOther(false); }}>{t.q4.dontKnow}</Button></p>
          {other && <Pick items={peopleItems.filter((p) => p.can_own !== false)} label={t.q4.pick} empty={t.q4.empty} onPick={(p) => { set({ owner: { source: "reporter", name: p.name } }); setOther(false); }} render={(p) => <><strong>{p.name}</strong> {p.team && <span className="n-muted">{p.team}</span>}</>} />}
          {a.owner && "unknown" in a.owner && <p className="n-muted">{t.q4.fallback}</p>}
          {a.owner && "source" in a.owner && <p>Chosen: <strong>{a.owner.name}</strong></p>}
        </>
      )}
      {step === 4 && (
        <>
          <North>{t.q5.lead}</North>
          <h3 style={{ margin: "8px 0" }}>{t.q5.areas}</h3>
          {opts.areas.length === 0 ? <p className="n-muted">{t.q5.areasEmpty}</p> : (
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              {opts.areas.map((ar) => <Chip key={ar} tone={a.areas.includes(ar) ? "active" : "default"} onClick={() => set({ areas: a.areas.includes(ar) ? a.areas.filter((x) => x !== ar) : [...a.areas, ar] })}>{ar}</Chip>)}
            </div>)}
          <h3 style={{ margin: "16px 0 8px" }}>{t.q5.people}</h3>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
            {a.affected.map((n) => <Chip key={n}>{n} <button type="button" aria-label={`Remove ${n}`} style={{ minHeight: 24, minWidth: 24 }} onClick={() => set({ affected: a.affected.filter((x) => x !== n) })}>x</button></Chip>)}
          </div>
          {a.affected.length === 0 && <p className="n-muted">{t.q5.peopleEmpty}</p>}
          <Pick items={peopleItems.filter((p) => !a.affected.includes(p.name))} label={t.q5.people} empty={t.q4.empty} onPick={(p) => set({ affected: [...a.affected, p.name] })} render={(p) => <><strong>{p.name}</strong> {p.team && <span className="n-muted">{p.team}</span>}</>} />
          <label style={{ display: "block", marginTop: 12, minHeight: 44 }}><input type="checkbox" role="switch" checked={a.affected_may_read} onChange={(e) => set({ affected_may_read: e.target.checked })} /> {t.q5.mayRead}<small className="n-muted" style={{ display: "block" }}>{t.q5.mayReadHelp}</small></label>
        </>
      )}
      {readback ? (
        <div role="status" style={{ marginTop: 12 }}><North>{t.readback(read[step] || "")}</North><Button variant="primary" disabled={busy} onClick={() => void yes()}>{t.yes}</Button> <Button onClick={() => setReadback(false)}>{t.change}</Button></div>
      ) : (
        <p style={{ marginTop: 12 }}><Button variant="primary" disabled={!valid || busy} onClick={() => void next()}>{t.next}</Button></p>
      )}
    </>
  );

  const review = (
    <div className="ds-card" style={{ padding: 16 }} role="region" aria-label={t.review.title}>
      <h2 style={{ marginTop: 0 }}>{t.review.title}</h2>
      {[["What is wrong", `${a.what}. ${a.saw}`, 0], [t.review.about, aboutText, 1], ["How hard it bites", a.bites ? `${BITES[a.bites.kind]}; ${a.bites.count || t.q3.notKnown}${a.bites.kind === "cost_money" ? `; ${unit ? `${a.bites.amount || t.q3.notKnown} ${a.bites.amount ? unit : ""}` : t.q3.noCurrency}` : ""}` : "", 2],
        [t.review.owner, ownerText ? ownerText : t.review.noOwner, 3], ["Areas and people", `${a.areas.join(", ")}; ${a.affected.join(", ")}`, 4]].map(([k, v, s]) => (
        <p key={String(k)}><strong>{k}:</strong> {v} <LinkButton onClick={() => { setStep(Number(s)); setReadback(false); }}>{t.review.edit}</LinkButton></p>
      ))}
      <p className="n-muted">{t.review.ends(endDate(days), days)}</p>
      {missing && <p role="status">{t.missing(missing)}</p>}
      <Button variant="primary" disabled={!!missing || busy} onClick={() => void save(5, true)}>{busy ? t.opening : t.open}</Button>
    </div>
  );

  return (
    <div className="ds-screen">
      <style>{STYLE}</style>
      {origin && (
        <div className="ds-card" style={{ padding: 12, marginBottom: 12 }} role="note">
          <strong>{origin}</strong> {origin === t.alertMissing ? null : <span className="n-muted">{links.alert ? t.origin.filled : t.origin.filledItem}</span>}{" "}
          <Button onClick={() => { setOrigin(null); setLinks({}); }}>{t.origin.remove}</Button>
        </div>
      )}
      <div className="ps-bar"><Button onClick={() => setSheet(!sheet)} aria-expanded={sheet}>{step < 5 ? t.questionOf(step + 1) : t.review.title}</Button>
        {sheet && <div className="ps-sheet" role="dialog" aria-label={t.summaryTitle}>{summary}<Button onClick={() => setSheet(false)}>{t.change}</Button></div>}</div>
      <div className="ps-grid">
        <div>{step < 5 ? question : review}{error && <p role="alert" className="state state-error">{error}</p>}
          <p style={{ marginTop: 16 }}><Button disabled={busy} onClick={async () => { if (await save(step)) nav("/centre/intent"); }}>{t.save}</Button></p></div>
        <div className="ps-side">{summary}</div>
      </div>
    </div>
  );
}
