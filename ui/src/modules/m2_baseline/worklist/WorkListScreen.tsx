import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { ApiError } from "../../../api/client";
import AgentChip from "../../../components/AgentChip";
import PageHead from "../../../components/PageHead";
import Panel from "../../../components/Panel";
import ScreenState from "../../../components/ScreenState";
import Sticky from "../../../components/Sticky";
import { useSession } from "../../../useSession";
import { useLoad } from "../../../components/useLoad";
import { CHANGED, confirmKpi, getWorkList, notifyChanged, type Suggestion, type WorkList } from "../api";
import BaselineSteps from "../BaselineSteps";
import { m2Work } from "../copy";
import KpiDetail from "./KpiDetail";
import ProvCell from "./ProvCell";
import TriageTable from "./TriageTable";
import { S } from "./layout";

const HOME = "/modules/m2_baseline";

/** Slide 4 and 5: the KPI work list of one baseline. Lens suggests measures for each charter problem from the industry pack;
 * a measure exists only when a person confirms or adds it. Then triage, owners and governance per measure. */
/** Everything the signed charter hands on, all four lists: what module 1 says goes on. */
const charterTotal = (d: WorkList): number => (d.charter_groups ? d.charter_groups.reduce((n, g) => n + g.items.length, 0) : d.problems.length);

export default function WorkListScreen() {
  const { baselineId = "" } = useParams();
  const { user } = useSession();
  const loaded = useLoad(() => getWorkList(baselineId), `worklist-${baselineId}`);
  const [fresh, setFresh] = useState<WorkList | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const [name, setName] = useState("");
  const [problem, setProblem] = useState("");
  const data = fresh ?? loaded.data;

  /** Runs one change; the server answers with the whole list, which replaces what is on screen. */
  const act = (p: Promise<WorkList>, done = "") => {
    p.then((v) => {
      setFresh(v);
      setNote(v.lens_note ?? done);
      notifyChanged(); // Lens's block reloads: a new measure or a person's edit changes what it has to say
    }).catch((e: unknown) => setNote(e instanceof ApiError ? e.message : m2Work.saveFailed));
  };
  useEffect(() => {
    // a change made in Lens's block (a definition used, an answer, a redraft) reloads this list
    const again = () => getWorkList(baselineId).then(setFresh).catch(() => undefined);
    window.addEventListener(CHANGED, again);
    return () => window.removeEventListener(CHANGED, again);
  }, [baselineId]);
  const confirm = (s: Suggestion) => act(confirmKpi(baselineId, { suggestion_id: s.id, problem_ids: s.problem_ids }));
  const locked = data?.baseline.state === "signed";
  const chosen = data?.kpis.find((k) => k.id === selected);
  const detail = useRef<HTMLDivElement>(null);
  useEffect(() => {
    // The detail opens below the whole table: bring it into view and put the keyboard there, so a click visibly does something.
    if (selected && detail.current) {
      detail.current.scrollIntoView?.({ block: "start", behavior: "smooth" });
      detail.current.focus({ preventScroll: true });
    }
  }, [selected]);
  const named = data?.kpis.filter((k) => !k.restricted).length ?? 0;
  const ownersDone = !!data && named > 0 && data.owners_complete >= named;

  return (
    <>
      <PageHead
        title={m2Work.title}
        eyebrow={data?.charter ? m2Work.fromCharter : data ? m2Work.fromEmpty : undefined}
        crumbs={[{ label: m2Work.crumbModules, to: "/" }, { label: m2Work.crumbBaseline, to: HOME }, { label: m2Work.crumbWorkList }]}
        sub={data ? m2Work.summary(charterTotal(data), data.kpis.length, data.owners_complete) : undefined}
      />
      <BaselineSteps baselineId={baselineId} signed={locked} />
      <ScreenState state={fresh ? "populated" : loaded.state} message={loaded.message} onRetry={loaded.retry}>
        {data ? (
          <>
            <Panel label="Lens">
              <AgentChip name="Lens" status="idle" />
              <p>{ownersDone ? m2Work.lensLineOwnersDone : m2Work.lensLine}</p>
              <p className="n-muted">{m2Work.lensBlock} <Link to={`${HOME}/preread/${baselineId}`}>{m2Work.lensMore}</Link></p>
              {!data.lens_available ? <p className="n-muted">{m2Work.lensNoModel}</p> : null}
              {note ? <p role="status" className="n-muted">{note}</p> : null}
            </Panel>

            {data.governance_note ? <p role="note" className="n-muted">{data.governance_note}</p> : null}

            {charterTotal(data) > 0 ? (
              <Panel eyebrow={m2Work.problemsEyebrow} title={m2Work.problemsTitle}>
                {(["problem", "pain_point"] as const).map((kind) => {
                  const rows = data.problems.filter((p) => (p.kind ?? "problem") === kind);
                  return rows.length > 0 ? (
                    <section key={kind}>
                      <h3>{m2Work.charterGroups[kind === "problem" ? "problems" : "pain_points"]}</h3>
                      <ul className="m1-list">
                        {rows.map((p) => (
                          <li key={p.id} style={S.problem}>
                            <div className="n-flex between wrap">
                              <strong>{p.title}</strong>
                              {!p.has_kpi ? <span className="n-muted">{m2Work.noMeasureYet}</span> : null}
                            </div>
                            <ul className="n-sticky-board">
                              {data.suggestions.filter((s) => s.problem_ids.includes(p.id)).map((s) => (
                                <li key={s.id}>
                                  <Sticky tone="copper" question={s.name}>
                                    <div className="tag">{m2Work.suggestionTag}</div>
                                    <div className="n-muted">{data.suggestion_label}</div>
                                    {s.definition?.value ? <ProvCell p={s.definition} /> : null}
                                    <button type="button" className="n-btn sm" disabled={locked} aria-label={`${m2Work.confirm}: ${s.name}`} onClick={() => confirm(s)}>
                                      {m2Work.confirm}
                                    </button>
                                  </Sticky>
                                </li>
                              ))}
                            </ul>
                          </li>
                        ))}
                      </ul>
                    </section>
                  ) : null;
                })}
                {(data.charter_groups ?? []).filter((g) => (g.key === "future_signals" || g.key === "levers") && g.items.length > 0).map((g) => (
                  <section key={g.key}>
                    <h3>{m2Work.charterGroups[g.key]}</h3>
                    <p className="n-muted">{m2Work.contextNote}</p>
                    <ul className="m1-list">
                      {g.items.map((i) => (
                        <li key={i.id}>{i.title}</li>
                      ))}
                    </ul>
                  </section>
                ))}
              </Panel>
            ) : null}

            <Panel eyebrow={m2Work.triageEyebrow} title={m2Work.triageTitle}>
              {data.kpis.length === 0 ? (
                <div className="n-empty">
                  <p className="ebody">{data.pack.available ? m2Work.emptyList : m2Work.noPack}</p>
                </div>
              ) : (
                <>
                  <TriageTable kpis={data.kpis} selected={selected} onSelect={setSelected} />
                  <p className="n-muted">{m2Work.unknownNote}</p>
                </>
              )}
            </Panel>

            {chosen && !chosen.restricted ? (
              <div ref={detail} tabIndex={-1} role="region" aria-label={`${m2Work.details}: ${chosen.name}`} style={{ outline: "none" }}>
                <KpiDetail id={baselineId} kpi={chosen} me={user?.display_name ?? ""} locked={locked} act={act} onClose={() => setSelected(null)} />
              </div>
            ) : null}

            <Panel title={m2Work.addTitle}>
              <p className="n-muted">{m2Work.addHelp}</p>
              <form
                className="n-flex wrap"
                onSubmit={(e) => {
                  e.preventDefault();
                  act(confirmKpi(baselineId, { name, problem_ids: problem ? [problem] : [] }));
                  setName("");
                }}
              >
                <label style={S.label}>
                  {m2Work.addName}
                  <input className="n-input" value={name} disabled={locked} onChange={(e) => setName(e.target.value)} />
                </label>
                {data.problems.length > 0 ? (
                  <label style={S.label}>
                    {m2Work.addForProblem}
                    <select className="n-select" value={problem} disabled={locked} onChange={(e) => setProblem(e.target.value)}>
                      <option value="">{m2Work.addForNone}</option>
                      {data.problems.map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.title}
                        </option>
                      ))}
                    </select>
                  </label>
                ) : null}
                <button type="submit" className="n-btn primary" disabled={locked || !name.trim()}>
                  {m2Work.add}
                </button>
              </form>
            </Panel>
          </>
        ) : null}
      </ScreenState>
    </>
  );
}
