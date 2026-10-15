import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { apiGet, apiSend } from "../../api/client";
import ScreenState from "../../components/ScreenState";
import { Button, Pill } from "../../design";
import "./checkin.css";
import { dateWords, days, homeCopy as h, stageName } from "./checkinCopy";
import { DayReviewer, OwnQuestion, PeoplePick, type Setup, type Values } from "./SeriesFields";

// Spec 38 Screen B (the series home) and Screen D (pause, resume, end). It is the stage view of a Weekly check-in.

interface Row { week_key: string; opens: string; closes: string; state: string; answered: number; of: number; items: number; settled: number }
interface Resp {
  series: { status: string; close_day: string; reviewer_name: string | null; extra_prompt: string | null; current_week: string | null; next_week_opens: string | null } | null;
  state: string; title: string; weeks: Row[]; not_answered: string[] | null; organiser: boolean; reviewer: boolean; participant: boolean; setup?: Setup;
}
type Act = "pause" | "resume" | "end";

const nextWorkingDay = (): string => {
  const d = new Date();
  do d.setDate(d.getDate() + 1); while (d.getDay() === 0 || d.getDay() === 6);
  return d.toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long" });
};

export default function SeriesHome({ intentId }: { intentId: string }) {
  const [r, setR] = useState<Resp | null | "failed">(null);
  const [panel, setPanel] = useState(false);
  const [act, setAct] = useState<Act | null>(null);
  const [reason, setReason] = useState("");
  const [v, setV] = useState<Values | null>(null);
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    apiGet<Resp>(`/api/intents/${intentId}/weeks`).then((d) => {
      setR(d);
      if (d.setup) setV({ area: d.setup.area, reporters: d.setup.reporters, close_day: d.setup.close_day, reviewer: d.setup.reviewer, extra: d.series?.extra_prompt ?? "" });
    }, () => setR("failed"));
  }, [intentId]);
  useEffect(load, [load]);

  if (r === null) return <ScreenState state="loading" />;
  if (r === "failed") return <ScreenState state="error" message={h.loadFailed} onRetry={load} />;
  const s = r.series;
  if (r.state === "draft" || !s) {
    return (
      <div className="ck"><h2 style={{ margin: 0 }}>{r.title || "Weekly check-in"}</h2><p>{h.draftLine}</p>
        {r.organiser && <div><Link className="ds-btn ds-btn--primary" to={`/centre/intent/new?type=pulse&draft=${intentId}`}>{h.finish}</Link></div>}</div>
    );
  }
  const now = r.weeks.find((w) => w.week_key === s.current_week);
  const earlier = r.weeks.filter((w) => w.week_key !== s.current_week).reverse();
  const ended = s.status === "ended";
  const tone = s.status === "running" ? "ok" : s.status === "paused" ? "late" : "draft";
  const closedRows = r.weeks.filter((w) => w.state === "closed");
  const same = !!v && !!r.setup && v.close_day === r.setup.close_day && v.reviewer === r.setup.reviewer && v.extra === (s.extra_prompt ?? "")
    && v.reporters.length === r.setup.reporters.length && v.reporters.every((x) => r.setup!.reporters.includes(x));

  const run = async (path: string, body: unknown, method: "POST" | "PUT" = "POST") => {
    setBusy(true); setMsg("");
    try { await apiSend(method, `/api/intents/${intentId}/${path}`, body); setAct(null); setReason(""); setMsg(method === "PUT" ? h.saved : ""); load(); }
    catch (e) { setMsg((e as { message?: string }).message || h.failed); }
    setBusy(false);
  };
  const toWeek = r.reviewer && !r.participant ? "review" : "week";

  return (
    <div className="ck">
      <div className="ck-row" style={{ justifyContent: "space-between" }}>
        <div>
          <h2 style={{ margin: 0 }}>{r.title}</h2>
          <p className="ck-row"><Pill tone={tone}>{s.status === "running" ? h.running : s.status === "paused" ? h.paused : h.ended}</Pill><span className="ck-muted">{days[s.close_day]}</span></p>
        </div>
        <div className="ck-row">
          {(r.organiser || r.reviewer) && <Button aria-expanded={panel} onClick={() => setPanel(!panel)}>{h.settings}</Button>}
          {r.organiser && !ended && <Button onClick={() => setAct(s.status === "paused" ? "resume" : "pause")}>{s.status === "paused" ? h.resume : h.pause}</Button>}
          {r.organiser && !ended && <Button onClick={() => setAct("end")}>{h.end}</Button>}
          {r.organiser && <Link className="ds-btn" to={`/centre/intent/${intentId}/share`}>{h.share}</Link>}
        </div>
      </div>
      {msg && <p role="status" className="ck-err">{msg}</p>}
      <div className="ck-grid ck-grid--home">
        <div className="ck">
          <div className="ds-card ck-panel">
            <h3>{h.thisWeek}</h3>
            {now ? (
              <>
                <p>{h.week(dateWords(now.opens, true), dateWords(now.closes))} <span className="ck-tag">{stageName[now.state] ?? now.state}</span></p>
                <p>{h.answered(now.answered, now.of)}</p>
                <div className="ck-row">
                  <Link className="ds-btn ds-btn--primary" to={`/centre/intent/${intentId}/${toWeek}`}>{toWeek === "review" ? h.readWeek : h.openWeek}</Link>
                  {r.participant && r.reviewer && <Link className="ds-btn" to={`/centre/intent/${intentId}/week`}>{h.answerMine}</Link>}
                </div>
              </>
            ) : <><p>{h.noWeek}</p>{r.organiser && !ended && <div><Button onClick={() => setAct("resume")}>{h.resume}</Button></div>}</>}
          </div>
          {r.not_answered && (
            <div className="ds-card ck-panel">
              <h3>{h.notAnswered}</h3>
              {r.not_answered.length === 0 ? <p>{h.everyone}</p> : <ul className="ck-list">{r.not_answered.map((n) => <li key={n}>{n}</li>)}</ul>}
            </div>
          )}
          {(r.organiser || r.reviewer) && (
            <div className="ds-card ck-panel">
              <h3>{h.counters}</h3>
              <div className="ck-strip">
                <div><span className="ck-muted">{h.weeksRun}</span><strong>{r.weeks.length}</strong></div>
                {now && <div><span className="ck-muted">{h.answersNow}</span><strong>{now.answered} of {now.of}</strong></div>}
                <div><span className="ck-muted">{h.settled}</span><strong>{closedRows.length ? closedRows.reduce((a, w) => a + w.settled, 0) : ""}</strong>{closedRows.length === 0 && <span className="ck-muted">{h.countersNa}</span>}</div>
              </div>
            </div>
          )}
        </div>
        <div className="ds-card ck-panel">
          <h3>{h.earlier}</h3>
          {earlier.length === 0 ? <p className="ck-muted">{h.earlierNone(dateWords(now?.closes))}</p> : (
            <ul className="ck-list">
              {earlier.map((w) => (
                <li key={w.week_key}>
                  <Link className="ds-link" to={`/centre/intent/${intentId}/${w.state === "closed" || !r.reviewer ? `week?week=${w.week_key}` : `review?week=${w.week_key}`}`}>{dateWords(w.opens, true)}</Link>
                  <span className="ck-tag" style={{ marginLeft: 8 }}>{stageName[w.state] ?? w.state}</span>
                  <br /><span className="ck-muted">{h.row(w.answered, w.items, w.settled)}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
      {panel && (
        <div className="ds-card ck-panel">
          <h3>{h.settings}</h3>
          <p><span className="ck-muted">{h.area}</span><br />{r.title.replace("Check-in: ", "")}<br /><span className="ck-muted">{h.areaNote}</span></p>
          {r.organiser && r.setup && v ? (
            <>
              <div className="ck-field"><span className="ck-label">Who reports each week?</span><PeoplePick setup={r.setup} area={v.area} value={v.reporters} onChange={(x) => setV({ ...v, reporters: x })} /></div>
              <DayReviewer setup={r.setup} v={v} set={(p) => setV({ ...v, ...p })} />
              <div className="ck-field"><span className="ck-label">{h.ownQuestion}</span>{!v.extra && <p className="ck-muted">{h.noOwn}</p>}<OwnQuestion setup={r.setup} v={v} set={(p) => setV({ ...v, ...p })} /></div>
              <p className="ck-muted">{h.applies(dateWords(s.next_week_opens))}</p>
              <div><Button variant="primary" disabled={same || busy || v.reporters.length < r.setup.minimum}
                onClick={() => void run("series", { reporters: v.reporters, close_day: v.close_day, reviewer: v.reviewer, extra_prompt: v.extra.trim() || null }, "PUT")}>{h.save}</Button></div>
            </>
          ) : (
            <p>{days[s.close_day]}. {s.reviewer_name}. {s.extra_prompt ?? h.noOwn}</p>
          )}
        </div>
      )}
      {act && (
        <div className="ck-dialog" role="dialog" aria-modal="true" aria-label={h.dialog[act].head}>
          <div>
            <h3 style={{ margin: 0 }}>{h.dialog[act].head}</h3>
            <p>{act === "resume" ? h.dialog.resume.line(nextWorkingDay()) : h.dialog[act].line as string}</p>
            {act !== "resume" && (
              <div className="ck-field"><label htmlFor="ck-why">{h.dialog.why}</label><input id="ck-why" type="text" maxLength={300} value={reason} onChange={(e) => setReason(e.target.value)} />
                {act === "end" && !reason.trim() && <span className="ck-muted">{h.dialog.whyNeeded}</span>}</div>
            )}
            <div className="ck-row">
              <Button variant="primary" disabled={busy || (act === "end" && !reason.trim())} onClick={() => void run(`series/${act}`, { reason })}>{h.dialog[act].button}</Button>
              <Button onClick={() => { setAct(null); setReason(""); }}>{h.dialog.notNow}</Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
