import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { ApiError } from "../../api/client";
import PageHead from "../../components/PageHead";
import Panel from "../../components/Panel";
import ScreenState from "../../components/ScreenState";
import Sticky from "../../components/Sticky";
import { useLoad } from "../../components/useLoad";
import { listBaselines, startBaseline } from "./api";
import { m2, m2Work } from "./copy";

const HOME = "/modules/m2_baseline";

function when(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "" : d.toLocaleDateString();
}

/** Module 2's entry: the baselines you have started, and the signed charters (or an empty list) to start one from. */
export default function BaselineHome() {
  const s = useLoad(listBaselines, "m2-baselines");
  const go = useNavigate();
  const [error, setError] = useState("");
  const start = (charterId: string | null) =>
    startBaseline(charterId)
      .then((v) => go(`${HOME}/preread/${v.baseline.id}`)) // first, "Give Lens what you already have"
      .catch((e: unknown) => setError(e instanceof ApiError ? e.message : m2Work.saveFailed));
  const data = s.data;
  return (
    <>
      <PageHead
        eyebrow={m2.eyebrow}
        title={m2.title}
        sub={m2.intro}
        crumbs={[{ label: m2Work.crumbModules, to: "/" }, { label: m2Work.crumbBaseline }]}
      />
      <ScreenState state={s.state} message={s.message} onRetry={s.retry}>
        {data ? (
          <>
            <Panel eyebrow={m2Work.crumbBaseline} title={m2Work.yourBaselines}>
              {data.baselines.length === 0 ? (
                <p className="n-muted">{m2Work.noBaselines}</p>
              ) : (
                <ul className="m1-list n-sticky-board">
                  {data.baselines.map((b) => (
                    <li key={b.id}>
                      <Sticky tone="teal" question={b.charter_outcome_id ? (b.charter_title ? m2Work.fromCharterNamed(b.charter_title, b.charter_signed_at ? when(b.charter_signed_at) : "") : m2Work.fromCharter) : m2Work.fromEmpty}>
                        <div className="n-muted n-sticky-pain">{m2Work.baselineRow(b.kpi_count)} · {when(b.created_at)}</div>
                        <Link className="n-btn sm" to={`${HOME}/baselines/${b.id}`}>
                          {m2Work.openBaseline}
                        </Link>
                      </Sticky>
                    </li>
                  ))}
                </ul>
              )}
            </Panel>
            <Panel title={m2Work.startTitle}>
              {data.charters.length === 0 ? <p className="n-muted">{m2Work.noCharters}</p> : null}
              <ul className="m1-list">
                {data.charters.filter((c) => c.baseline_id === null).map((c) => (
                  <li key={c.outcome_id} className="n-flex between wrap">
                    <span>{c.title ? `${c.title} · ` : ""}{m2Work.charterRow(c.problem_count, when(c.signed_at))}</span>
                    <button type="button" className="n-btn primary" onClick={() => start(c.outcome_id)}>
                      {m2Work.startFromCharter}
                    </button>
                  </li>
                ))}
              </ul>
              <p className="n-muted">{m2Work.startEmptyHelp}</p>
              <button type="button" className="n-btn" onClick={() => start(null)}>
                {m2Work.startEmpty}
              </button>
              {error ? <p role="alert" className="state state-error">{error}</p> : null}
            </Panel>
          </>
        ) : null}
      </ScreenState>
    </>
  );
}
