import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";

import V3Frame from "../Frame";
import { CENTRE, SOURCE, STATUS, getSkill, listSkills, when, type Centre, type Source, type SkillDetail, type SkillRow, type SkillStatus } from "../action/actionApi";
import "../action/action.css";
import { usePhone } from "./k/usePhone";
import "./skills.css";

function Pick<T extends string>({ label, all, value, onChange, names }: { label: string; all: T[]; value: T | ""; onChange: (v: T | "") => void; names: Record<T, string> }) {
  return (
    <fieldset>
      <legend>{label}</legend>
      {(["", ...all] as (T | "")[]).map((k) => (
        <button key={k || "all"} type="button" className="act-pill" aria-pressed={value === k} onClick={() => onChange(k)}>{k ? names[k] : "All"}</button>
      ))}
    </fieldset>
  );
}

/** Status colours mean one thing: in use is done, waiting needs a person, retired is just information. */
const TONE: Record<SkillStatus, string> = { in_use: "done", waiting: "needs", retired: "info" };
const Status = ({ s }: { s: SkillRow }) => <span className={`v3-pill ${TONE[s.status]}`}>{STATUS[s.status]}</span>;
const From = ({ s }: { s: SkillRow }) => (s.source === "office" ? <span className="v3-pill harbor">{SOURCE[s.source]}</span> : <>{SOURCE[s.source]}</>);
const tested = (s: SkillRow) => (s.tested ? `${s.tested.passed} of ${s.tested.total} known answers` : "Not tested");
const Para = ({ title, text }: { title: string; text: string }) => <><h3 className="act-h3">{title}</h3><p style={{ margin: 0 }}>{text}</p></>;
const List = ({ title, rows }: { title: string; rows: string[] }) =>
  rows.length ? <><h3 className="act-h3">{title}</h3><ul style={{ margin: 0, paddingLeft: 20, lineHeight: 1.6 }}>{rows.map((r, i) => <li key={i}>{r}</li>)}</ul></> : null;

export default function SkillsPage() {
  const [rows, setRows] = useState<SkillRow[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [centre, setCentre] = useState<Centre | "">("");
  const [source, setSource] = useState<Source | "">("");
  const [status, setStatus] = useState<SkillStatus | "">("");
  const [q, setQ] = useState("");
  const [sel, setSel] = useState<string | null>(null);
  const [detail, setDetail] = useState<SkillDetail | null>(null);
  const [detailFailed, setDetailFailed] = useState(false);
  const phone = usePhone();
  const side = useRef<HTMLDivElement>(null);
  const pick = (id: string) => { setSel(id); if (phone) setTimeout(() => side.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 50); };

  const load = () => { setFailed(false); listSkills().then((r) => setRows(r.skills), () => setFailed(true)); };
  useEffect(load, []);
  useEffect(() => {
    setDetail(null);
    setDetailFailed(false);
    if (sel) getSkill(sel).then(setDetail, () => setDetailFailed(true));
  }, [sel]);

  const shown = useMemo(() => (rows ?? []).filter((s) =>
    (!centre || s.centre === centre) && (!source || s.source === source) && (!status || s.status === status) &&
    (!q.trim() || `${s.name} ${s.goal}`.toLowerCase().includes(q.trim().toLowerCase()))), [rows, centre, source, status, q]);

  if (failed) return <V3Frame><p className="v3-err act-empty" role="alert">The skill library did not load. <button type="button" onClick={load}>Try again</button></p></V3Frame>;
  if (!rows) return <V3Frame><p className="v3-mute act-empty" role="status">Loading the skill library...</p></V3Frame>;
  if (!rows.length) return <V3Frame><div className="act-empty"><h1>Skills Harbor uses</h1><p className="v3-mute">There are no skills in this office yet.</p></div></V3Frame>;

  const waiting = rows.filter((s) => s.status === "waiting");
  const row = rows.find((r) => r.id === sel);
  const detailPane = (
        <aside className="act-detail" aria-label="Selected skill">
          {!row ? <p className="v3-mute">Pick a skill to read what it does.</p> : (
            <>
              <div>
                <span className="v3-kicker">Selected skill</span>
                <h2>{row.name}</h2>
                <span className="sk-meta">{CENTRE[row.centre]} · <From s={row} /> · v{row.version} · <Status s={row} /></span>
              </div>
              {detailFailed && <p className="v3-err" role="alert">The detail did not load.</p>}
              {!detail && !detailFailed && <p className="v3-mute" role="status">Loading...</p>}
              {detail && (
                <>
                  <Para title="Goal" text={detail.goal} />
                  <Para title="When Harbor uses it" text={detail.when} />
                  <Para title="What it needs" text={detail.inputs} />
                  <Para title="What it gives" text={detail.output} />
                  <List title="Its steps" rows={detail.steps} />
                  <List title="Tools it may call" rows={detail.tools} />
                  <List title="Checks" rows={detail.checks} />
                  <List title="Never does" rows={detail.never} />
                  {detail.cache && <Para title="Cache" text={`${detail.cache.answers} answers cached; ${detail.cache.golden} golden questions pre-computed after each run`} />}
                  <List title="Version history" rows={detail.history.map((h) => `v${h.v} · ${h.change} · ${h.by}, ${when(h.at)}`)} />
                </>
              )}
            </>
          )}
        </aside>
  );
  return (
    <V3Frame>
      <div className="sk-page">
      <section className="act-head" aria-labelledby="h-skills">
        <div>
          <span className="act-eyebrow">Knowledge · Skills</span>
          <h1 id="h-skills">Skills Harbor uses</h1>
          <p className="v3-mute">Harbor reads the names first and loads one skill when it needs it. A person admits every new skill before it runs.</p>
        </div>
        <div className="lib-bar">
          <Pick label="Centre" all={Object.keys(CENTRE) as Centre[]} value={centre} onChange={setCentre} names={CENTRE} />
          <Pick label="Source" all={Object.keys(SOURCE) as Source[]} value={source} onChange={setSource} names={SOURCE} />
          <Pick label="Status" all={Object.keys(STATUS) as SkillStatus[]} value={status} onChange={setStatus} names={STATUS} />
          <input type="search" aria-label="Search skills" placeholder="Search skills" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
      </section>
      <div className="act-main">
        <section className="act-queue" aria-label="Skill library">
          {waiting.length > 0 && (
            <div className="act-item sk-waiting">
              <span className="v3-kicker">Waiting for you: {waiting.length}</span>
              {waiting.map((w) => <p key={w.id}><Link to={`/v3/skill/${encodeURIComponent(w.id)}`}>{w.name}</Link> <span className="v3-mute">Review and admit it before Harbor uses it.</span></p>)}
            </div>
          )}
          <h2>Skill library</h2>
          <p className="v3-mute">{shown.length} of {rows.length} skills shown</p>
          {!shown.length ? <p className="v3-mute">No skill matches those filters.</p> : (
            phone ? (
              <ul className="sk-cards">{shown.map((s) => (
                <li key={s.id} className={s.id === sel ? "on" : undefined}>
                  <button type="button" aria-pressed={s.id === sel} onClick={() => pick(s.id)}>
                    <span className="sk-top"><b>{s.name}</b><Status s={s} /></span>
                    <span className="sk-goal">{s.goal}</span>
                    <span className="sk-meta">{CENTRE[s.centre]} · <From s={s} /> · v{s.version} · {tested(s)} · used {s.used}</span>
                  </button>
                  {s.id === sel && <div ref={side}>{detailPane}</div>}
                </li>))}
              </ul>
            ) : <table className="lib-tbl">
              <thead><tr><th>Skill</th><th>Goal</th><th>Centre</th><th>Source</th><th>Version</th><th>Tested</th><th>Used</th><th>Last changed</th></tr></thead>
              <tbody>{shown.map((s) => (
                <tr key={s.id} data-on={s.id === sel} className="sk-row" onClick={() => pick(s.id)}>
                  <td>
                    <button type="button" className="lib-name" aria-pressed={s.id === sel} onClick={(e) => { e.stopPropagation(); pick(s.id); }}>{s.name}</button>
                    <div><Status s={s} /></div>
                  </td>
                  <td>{s.goal}</td><td>{CENTRE[s.centre]}</td><td><From s={s} /></td>
                  <td className="num">v{s.version}</td><td>{tested(s)}</td><td className="num">{s.used}</td>
                  <td>{s.last_changed ? `${s.last_changed.by} · ${when(s.last_changed.at)}` : ""}</td>
                </tr>
              ))}</tbody>
            </table>
          )}
        </section>
        {!phone && detailPane}
      </div>
      </div>
    </V3Frame>
  );
}
