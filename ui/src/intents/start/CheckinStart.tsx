import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { apiGet, apiSend } from "../../api/client";
import ScreenState from "../../components/ScreenState";
import { Button, SideCard } from "../../design";
import "../checkin/checkin.css";
import { dateWords, days, startCopy as t } from "../checkin/checkinCopy";
import { AreaPick, DayReviewer, OwnQuestion, PeoplePick, previewLine, usePhone, type Setup, type Values } from "../checkin/SeriesFields";
import type { StartProps } from "../IntentNew";

// Spec 38 Screen A: the four start questions of the Weekly check-in, one block at a time, with "What happens" beside them.

interface Resp { organiser: boolean; setup?: Setup }

const startNone = t.noOwn;

export default function CheckinStart({ draftId }: StartProps) {
  const nav = useNavigate();
  const phone = usePhone();
  const [setup, setSetup] = useState<Setup | null | "failed">(null);
  const [v, setV] = useState<Values>({ area: null, reporters: [], close_day: "fri", reviewer: "", extra: "" });
  const [step, setStep] = useState(0);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [showPlan, setShowPlan] = useState(false);

  const load = useCallback((day?: string, area?: string | null) => {
    const q = [day && `close_day=${day}`, area && `area=${encodeURIComponent(area)}`].filter(Boolean).join("&");
    apiGet<Resp>(`/api/intents/${draftId}/weeks${q ? `?${q}` : ""}`).then((r) => {
      if (!r.setup) return setSetup("failed");
      setSetup(r.setup);
      setV((o) => (o.reviewer ? o : { area: r.setup!.area, reporters: r.setup!.reporters, close_day: r.setup!.close_day, reviewer: r.setup!.reviewer, extra: "" }));
    }, () => setSetup("failed"));
  }, [draftId]);
  useEffect(() => load(), [load]);

  if (setup === null) return <ScreenState state="loading" />;
  if (setup === "failed") return <ScreenState state="error" message={t.loadFailed} onRetry={() => load()} />;

  const set = (p: Partial<Values>) => { setV((o) => ({ ...o, ...p })); if (p.close_day) load(p.close_day); };
  const valid = [!!v.area, v.reporters.length >= setup.minimum];
  const missing = [!valid[0] && t.missingArea, !valid[1] && t.missingPeople(setup.minimum)].filter(Boolean) as string[];
  const body = { ...(v.area ? { area: v.area } : {}), reporters: v.reporters, close_day: v.close_day, reviewer: v.reviewer, extra_prompt: v.extra.trim() || null };
  const save = async (go: boolean) => {
    setBusy(true); setMsg("");
    try {
      await apiSend("PUT", `/api/intents/${draftId}/series`, body);
      if (go) {
        await apiSend("POST", `/api/intents/${draftId}/series/start`, {});
        nav(`/centre/intent/${draftId}`);
      } else setMsg(t.saved);
    } catch (e) {
      setMsg((e as { message?: string }).message || t.failed);
    }
    setBusy(false);
  };

  const who = setup.people.find((p) => p.id === v.reviewer)?.name ?? "";
  const summary = [v.area ?? "", `${t.people(v.reporters.length)}: ${setup.people.filter((p) => p.id && v.reporters.includes(p.id)).map((p) => p.name).join(", ")}`,
    `${days[v.close_day]}, ${who}`, v.extra || startNone];
  const block = (i: number, lead: string, field: React.ReactNode, ok: boolean) => (
    <div className="ds-card ck-panel" key={i}>
      {step === i ? (
        <>
          {i !== 2 && <h2>{lead}</h2>}{/* question 3's day field carries the same words as its label */}
          {field}
          {i < 3 && <div><Button variant="primary" disabled={!ok} onClick={() => setStep(i + 1)}>{t.next}</Button></div>}
        </>
      ) : (
        <div className="ck-row" style={{ justifyContent: "space-between" }}>
          <span><span className="ck-muted">{lead}</span><br />{summary[i]}</span>
          <Button onClick={() => setStep(i)}>{t.change}</Button>
        </div>
      )}
    </div>
  );

  const plan = (
    <SideCard title={t.what}>
      <p>{previewLine(setup.preview, (s) => dateWords(s))}</p>
      <p>{t.northLine}</p>
    </SideCard>
  );

  return (
    <div className="ck">
      <div><h2 style={{ margin: 0 }}>{t.heading}</h2><p className="ck-muted">{t.sub}</p></div>
      <div className="ck-grid" style={{ gridTemplateColumns: phone ? "minmax(0, 1fr)" : "minmax(0, 1fr) minmax(0, 340px)" }}>
        <div className="ck">
          <strong>{t.northAsks}</strong>
          {block(0, t.q1, <AreaPick setup={setup} value={v.area} onChange={(a) => { set({ area: a }); load(v.close_day, a); }} />, !!valid[0])}
          {block(1, t.q2, <PeoplePick setup={setup} area={v.area} value={v.reporters} onChange={(r) => set({ reporters: r })} />, !!valid[1])}
          {block(2, t.q3, <DayReviewer setup={setup} v={v} set={set} />, true)}
          {block(3, t.q4, <OwnQuestion setup={setup} v={v} set={set} />, true)}
          {phone && <><div><Button aria-expanded={showPlan} onClick={() => setShowPlan(!showPlan)}>{t.what}</Button></div>{showPlan && plan}</>}
          <div className="ck-row">
            <Button variant="primary" disabled={busy || missing.length > 0} onClick={() => void save(true)}>{t.start}</Button>
            <Button disabled={busy} onClick={() => void save(false)}>{t.saveDraft}</Button>
            <Link to="/centre/intent/new" className="ds-link">{t.cancel}</Link>
          </div>
          {missing.length > 0 && <p className="ck-muted">{t.missing(missing)}</p>}
          {msg && <p role="status" className="ck-err">{msg}</p>}
        </div>
        {!phone && <div>{plan}</div>}
      </div>
    </div>
  );
}
