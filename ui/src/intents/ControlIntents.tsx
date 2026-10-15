import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError, apiGet } from "../api/client";
import { getCatalogue, listCompanies, setCentre, type ControlCompany } from "../api/control";
import ScreenState from "../components/ScreenState";
import { useLoad } from "../components/useLoad";
import { controlText } from "../pages/controlCopy";
import { Pill, PageFrame, type PillTone } from "../design";

// Super admin: which companies use the Intent centre, and that intents exist. Never what is in them (spec 48 screen E, A-074).

const t = {
  title: "Intents per company", back: "Back to Control", centre: "Centre", counts: "Counts", intents: "Intents", name: "Intent centre",
  offNote: "Off hides the centre for everyone in the company. Intents and their records are kept.", saved: "Saved.",
  none: "This company has no intents yet.", noActivity: "No activity yet.", private: "Title private to the company",
  use: "Centre use", useNone: "This company has not opened an intent.", month: "Month", closedCol: "Closed", cancelledCol: "Cancelled",
  windows: { "6m": "Last 6 months", "12m": "Last 12 months" } as Record<string, string>,
  note: "Control sees that intents exist. It never sees what is in them.", failed: "That did not work. Please try again.",
  types: { initiative: "Initiative", brainstorm: "Brainstorm", pulse: "Weekly check-in", problem: "Problem", decision: "Decision" } as Record<string, string>,
  cols: { open: "Open", in_session: "In session", closing: "Closing", closed: "Closed", cancelled: "Cancelled" } as Record<string, string>,
  states: { open: "Open", in_session: "In session", closing: "Closing", closed: "Closed", cancelled: "Cancelled" } as Record<string, string>,
};

interface Summary {
  company_id: string; centre_on: boolean; titles_private: boolean; total: number; overdue: number; at_risk: number; last_activity: string | null;
  by_type: Record<string, Record<string, number>>;
  centre_use: { opened_any: boolean; time_zone: string; months: { month: string; opened: Record<string, number>; closed: number; cancelled: number }[] };
}
interface Existence { title: string | null; title_private: boolean; type: string; state: string; areas: string[]; people_count: number; opened: string | null; ends: string | null; clock: string; bucket: string }

const style = `
.ci-card { padding: 16px 18px; margin-bottom: 14px; display: flex; flex-direction: column; gap: 10px; }
.ci-card h2 { margin: 0; font-size: 16px; }
.ci-pick { display: flex; flex-direction: column; gap: 4px; font-size: 12px; color: var(--ds-ink-muted); max-width: 320px; margin-bottom: 14px; }
.ci-pick select { min-height: 40px; padding: 8px 10px; border-radius: 8px; border: 1px solid var(--ds-line-2); background: var(--ds-ground); color: var(--ds-ink); font: inherit; font-size: 14px; }
.ci-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; min-height: 44px; font-size: 14px; }
.ci-row small { display: block; color: var(--ds-ink-muted); font-size: 12px; }
.ds-screen input.ci-sw[type="checkbox"] { appearance: none; flex: none; width: 40px; min-width: 40px; min-height: 22px; height: 22px; border-radius: 999px; background: var(--ds-line-2); position: relative; cursor: pointer; margin: 0; }
.ci-sw::after { content: ""; position: absolute; top: 3px; left: 3px; width: 16px; height: 16px; border-radius: 50%; background: var(--ds-ink); transition: left .15s ease; }
.ds-screen input.ci-sw:checked { background: var(--ds-teal); } .ci-sw:checked::after { left: 21px; }
.ci-sw:focus-visible { outline: 2px solid var(--ds-teal-bright); outline-offset: 2px; }
.ci-stats { display: flex; gap: 24px; flex-wrap: wrap; font-size: 14px; color: var(--ds-ink-soft); }
.ci-tbl { width: 100%; border-collapse: collapse; font-size: 13px; }
.ci-tbl th, .ci-tbl td { text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--ds-line); vertical-align: top; }
.ci-grey { color: var(--ds-ink-muted); }
@media (max-width: 760px) {
  .ci-tbl.ci-cards, .ci-tbl.ci-cards tbody, .ci-tbl.ci-cards tr, .ci-tbl.ci-cards td { display: block; width: 100%; box-sizing: border-box; }
  .ci-tbl.ci-cards thead { display: none; }
  .ci-tbl.ci-cards tr { border: 1px solid var(--ds-line); border-radius: 10px; margin-bottom: 10px; padding: 6px 4px; }
}
`;

const day = (iso: string | null) => (iso ? new Date(iso).toLocaleDateString("en-GB", { dateStyle: "medium" }) : "");
const tone = (b: string): PillTone => (b === "overdue" || b === "late" ? "late" : b === "at_risk" ? "failed" : b === "done" ? "ok" : "open");

export default function ControlIntents() {
  const co = useLoad(listCompanies, "ci-companies");
  const cat = useLoad(getCatalogue, "ci-cat");
  const rows: ControlCompany[] = co.data?.companies ?? [];
  const [sel, setSel] = useState("ardmore");
  const id = rows.some((c) => c.id === sel) ? sel : rows[0]?.id ?? "";
  const [sum, setSum] = useState<Summary | null>(null);
  const [list, setList] = useState<Existence[] | null>(null);
  const [fail, setFail] = useState<string | null>(null);
  const [on, setOn] = useState<boolean | null>(null);
  const [saved, setSaved] = useState(false);
  const [win, setWin] = useState("6m");
  useEffect(() => {
    if (!id) return;
    let live = true;
    setSum(null); setList(null); setFail(null); setSaved(false);
    const q = encodeURIComponent(id);
    Promise.all([apiGet<Summary>(`/api/control/intents/summary?company_id=${q}&window=${win}`), apiGet<{ rows: Existence[] }>(`/api/control/companies/${q}/intents`)]).then(
      ([s, l]) => { if (live) { setSum(s); setOn(s.centre_on); setList(l.rows); } },
      (e: unknown) => { if (live) setFail(e instanceof ApiError && e.status < 500 ? e.message : t.failed); });
    return () => { live = false; };
  }, [id, win]);
  const flip = async (v: boolean) => {
    try { await setCentre(id, "intent", v); setOn(v); setSaved(true); setFail(null); } catch { setFail(t.failed); }
  };
  const label = cat.data?.centres.find((c) => c.id === "intent")?.name ?? t.name;
  return (
    <PageFrame title={t.title} crumbs={<Link to="/centre/control">{t.back}</Link>}>
      <style>{style}</style>
      <ScreenState state={co.state === "populated" && rows.length === 0 ? "empty" : co.state} message={rows.length === 0 && co.state === "populated" ? controlText.centres.none : co.message} onRetry={co.retry}>
        <label className="ci-pick">{controlText.centres.pick}
          <select value={id} onChange={(e) => setSel(e.target.value)}>{rows.map((c) => <option key={c.id} value={c.id}>{c.display ?? c.id}</option>)}</select>
        </label>
        {fail ? <p role="alert" style={{ color: "var(--ds-amber)" }}>{fail}</p> : null}
        <section className="ds-card ci-card" aria-label={t.centre}>
          <h2>{t.centre}</h2>
          <label className="ci-row">
            <span>{label}<small>{saved ? t.saved : t.offNote}</small></span>
            <input className="ci-sw" type="checkbox" role="switch" aria-label={label} checked={!!on} disabled={on === null} onChange={(e) => void flip(e.target.checked)} />
          </label>
        </section>
        <ScreenState state={fail ? "populated" : sum && list ? "populated" : "loading"}>
          {sum && list ? (
            <>
              <section className="ds-card ci-card" aria-label={t.counts}>
                <h2>{t.counts}</h2>
                {sum.total === 0 ? <p className="ci-grey" style={{ margin: 0 }}>{t.none}</p> : (
                  <div style={{ overflowX: "auto" }}><table className="ci-tbl">
                    <thead><tr><th>Type</th>{Object.values(t.cols).map((c) => <th key={c}>{c}</th>)}<th>Total</th></tr></thead>
                    <tbody>
                      {Object.entries(t.types).map(([k, name]) => (
                        <tr key={k}><td>{name}</td>{Object.keys(t.cols).map((s) => <td key={s}>{sum.by_type[k]?.[s] ?? 0}</td>)}<td>{Object.values(sum.by_type[k] ?? {}).reduce((a, n) => a + n, 0)}</td></tr>
                      ))}
                    </tbody>
                  </table></div>
                )}
                <div className="ci-stats"><span>{sum.overdue} overdue</span><span>{sum.at_risk} at risk</span><span>{sum.last_activity ? `Last activity ${day(sum.last_activity)}` : t.noActivity}</span></div>
              </section>
              <section className="ds-card ci-card" aria-label={t.use}>
                <h2>{t.use}</h2>
                <label className="ci-pick" style={{ marginBottom: 0 }}><select aria-label={t.use} value={win} onChange={(e) => setWin(e.target.value)}>{Object.entries(t.windows).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
                {!sum.centre_use.opened_any ? <p className="ci-grey" style={{ margin: 0 }}>{t.useNone}</p> : (
                  <div style={{ overflowX: "auto" }}><table className="ci-tbl">
                    <thead><tr><th>{t.month}</th>{Object.values(t.types).map((n) => <th key={n}>{n}</th>)}<th>{t.closedCol}</th><th>{t.cancelledCol}</th></tr></thead>
                    <tbody>{sum.centre_use.months.map((m) => (
                      <tr key={m.month}><td>{m.month}</td>{Object.keys(t.types).map((k) => <td key={k}>{m.opened[k] ?? 0}</td>)}<td>{m.closed}</td><td>{m.cancelled}</td></tr>
                    ))}</tbody>
                  </table></div>
                )}
              </section>
              <section className="ds-card ci-card" aria-label={t.intents}>
                <h2>{t.intents}</h2>
                {list.length === 0 ? <p className="ci-grey" style={{ margin: 0 }}>{t.none}</p> : (
                  <table className="ci-tbl ci-cards">
                    <thead><tr><th>Title</th><th>Type</th><th>State</th><th>Areas</th><th>People</th><th>Opened</th><th>Ends</th><th>Clock</th></tr></thead>
                    <tbody>
                      {list.map((r, i) => (
                        <tr key={i}>
                          <td>{r.title_private || r.title === null ? <span className="ci-grey">{t.private}</span> : r.title}</td>
                          <td>{t.types[r.type]}</td><td>{t.states[r.state]}</td><td>{r.areas.join(", ") || "No area"}</td><td>{r.people_count}</td>
                          <td>{day(r.opened)}</td><td>{day(r.ends)}</td><td><Pill tone={tone(r.bucket)}>{r.clock}</Pill></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </section>
            </>
          ) : null}
        </ScreenState>
        <p className="ci-grey">{t.note}</p>
      </ScreenState>
    </PageFrame>
  );
}
