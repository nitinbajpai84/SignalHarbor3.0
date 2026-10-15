import { useState } from "react";

import { ApiError } from "../../../api/client";
import Panel from "../../../components/Panel";
import ScreenState from "../../../components/ScreenState";
import StatusPill from "../../../components/StatusPill";
import { useLoad } from "../../m1_intent/useLoad";
import { getBenchmarks, mapBenchmark, uploadBenchmarks, type Benchmarks } from "./api";
import { m3Intake as T } from "./copy";
import FilePicker from "./FilePicker";

/** The customer's second action: the figures they already report. A file, the matches, and one dropdown per line Lens could not match. */
export default function BenchmarkPanel({ assessmentId }: { assessmentId: string }) {
  const first = useLoad<Benchmarks>(() => getBenchmarks(assessmentId), `m3-bench-${assessmentId}`);
  const [fresh, setFresh] = useState<Benchmarks | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const view = fresh ?? first.data;

  async function map(index: number, measureId: string) {
    setProblem(null);
    try {
      setFresh(await mapBenchmark(assessmentId, index, measureId));
    } catch (e) {
      setProblem(e instanceof ApiError && e.message ? e.message : T.actionFailed);
    }
  }

  return (
    <Panel title={T.benchTitle}>
      <p className="n-muted">{T.benchHelp}</p>
      {view?.measures.some((m) => m.from_profile) ? <p className="n-muted">{T.benchFromProfile}</p> : null}
      <FilePicker label={T.chooseFile} button={T.benchUpload} send={async (n, d) => setFresh(await uploadBenchmarks(assessmentId, n, d))} />
      <ScreenState state={first.state} message={first.message} onRetry={first.retry}>
        {view ? (
          <>
            {problem ? (
              <p role="alert" className="state state-error">
                {problem}
              </p>
            ) : null}
            {view.measures.length > 0 ? (
              <div className="n-table-wrap">
                <table className="n-table">
                  <caption className="n-muted">{T.benchMatched}</caption>
                  <thead>
                    <tr>
                      <th scope="col">{T.measure}</th>
                      <th scope="col">{T.figure}</th>
                      <th scope="col">{T.periodEnd}</th>
                      <th scope="col">{T.cameFrom}</th>
                      <th scope="col">{T.givenBy}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {view.measures.map((m) => (
                      <tr key={m.measure_id}>
                        <td>{m.measure_name}</td>
                        {m.restricted ? (
                          <td colSpan={4} className="n-muted" />
                        ) : (
                          <>
                            <td>{`${m.figure ?? ""}${m.unit ? ` ${m.unit}` : ""}`}</td>
                            <td>{m.period_end ?? ""}</td>
                            <td>{m.from_profile && m.came_from ? T.from(m.came_from) : (m.came_from ?? "")}</td>
                            <td>{m.given_by}</td>
                          </>
                        )}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="n-muted">{T.empty}</p>
            )}
            {view.unmatched.length > 0 ? (
              <div>
                <h3>{T.unmatchedTitle}</h3>
                <p className="n-muted">{T.unmatchedHelp}</p>
                <ul className="m1-list">
                  {view.unmatched.map((u) => (
                    <li key={u.index}>
                      <strong>{u.line}</strong> {u.figure !== null ? `${u.figure}${u.unit ? ` ${u.unit}` : ""}` : <StatusPill tone="warning">{T.noFigure}</StatusPill>}{" "}
                      {u.figure !== null ? (
                        <select aria-label={`${T.mapTo}: ${u.line}`} defaultValue="" onChange={(e) => e.target.value && void map(u.index, e.target.value)}>
                          <option value="">{T.choose}</option>
                          {view.choices.map((c) => (
                            <option key={c.id} value={c.id}>
                              {c.name}
                            </option>
                          ))}
                        </select>
                      ) : null}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
            {view.waiting_for.length > 0 ? (
              <p className="n-muted">
                {T.benchWaiting}: {view.waiting_for.map((w) => w.name).join(", ")}
              </p>
            ) : null}
          </>
        ) : null}
      </ScreenState>
    </Panel>
  );
}
