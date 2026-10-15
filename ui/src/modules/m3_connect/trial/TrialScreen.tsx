import { useState } from "react";
import { useParams } from "react-router-dom";

import PageHead from "../../../components/PageHead";
import ScreenState from "../../../components/ScreenState";
import StatusPill, { type PillTone } from "../../../components/StatusPill";
import { useSession } from "../../../useSession";
import { useLoad } from "../../m1_intent/useLoad";
import { getAssessment } from "../api";
import ConnectSteps from "../ConnectSteps";
import { m3 } from "../copy";
import NiraNext from "../NiraNext";
import { checkRule, compileRules, getFindings, getTrial, runTrial, type FindingsView, type Group, type Result, type TrialRow } from "./api";
import { acceptedSummary, plainText, shortReason, splitAccepted } from "../plainText";
import { trialText as t } from "./copy";
import Scoreboard from "./Scoreboard";

const TONE: Record<Result, PillTone> = { matches: "success", gap: "warning", cannot: "muted" };
const GROUPS: Group[] = ["ready", "unclear", "unknown"];

/** A missing figure is never shown as zero. */
function figure(v: number | null | undefined, unit?: string | null): string {
  if (v === null || v === undefined) return t.notAvailable;
  return `${v.toLocaleString("en", { maximumFractionDigits: 2 })}${unit ? ` ${unit}` : ""}`;
}

function RuleLine({ row }: { row: TrialRow }) {
  const r = row.rule;
  if (!r) return null;
  if (r.state === "could_not_compile") {
    return (
      <details className="n-muted">
        <summary>{t.noRule}. {t.why}</summary>
        {plainText(r.reason ?? "")}
      </details>
    );
  }
  return (
    <div className="n-muted">
      {t.rulePrefix}
      {r.words}
      {r.origin === "pack hint" ? ` (${t.suggestion})` : ""}
    </div>
  );
}

function TrialTable({ rows, canCheck, onCheck }: { rows: TrialRow[]; canCheck: boolean; onCheck: (m: string) => void }) {
  return (
    <div style={{ overflowX: "auto" }}>
      <table className="n-table">
        <thead>
          <tr>
            {Object.values(t.head).map((h) => (
              <th key={h}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) =>
            r.restricted ? (
              <tr key={r.measure}>
                <td colSpan={6}>{t.restricted}</td>
              </tr>
            ) : (
              <tr key={r.measure}>
                <td>
                  <strong>{r.name}</strong>
                  <RuleLine row={r} />
                </td>
                <td className="num">{figure(r.our_figure, r.unit)}{r.group_note ? <div className="n-muted">{r.group_note}</div> : null}</td>
                <td className="num">{figure(r.their_figure, r.unit)}</td>
                <td>
                  <StatusPill tone={TONE[r.result ?? "cannot"]}>{t.result[r.result ?? "cannot"]}</StatusPill>
                </td>
                <td><span title={plainText(r.likely_reason_lens || r.likely_reason || r.missing || "")}>{shortReason(r.likely_reason_lens || r.likely_reason || r.missing || "")}</span></td>
                <td>
                  {r.rule?.state === "checked" ? (
                    r.rule.auto_checked ? t.autoChecked : t.checkedBy(r.rule.checked_by ?? "")
                  ) : r.rule?.state === "draft" ? (
                    <>
                      <span className="n-muted">{t.notChecked}</span>{" "}
                      {canCheck ? (
                        <button type="button" className="n-btn sm" aria-label={t.checkLabel(r.name)} onClick={() => onCheck(r.measure)}>
                          {t.check}
                        </button>
                      ) : null}
                    </>
                  ) : null}
                </td>
              </tr>
            ),
          )}
        </tbody>
      </table>
    </div>
  );
}

function FindingsColumns({ data }: { data: FindingsView }) {
  const all = Object.values(data.measures);
  return (
    <section aria-label={t.findingsTitle} style={{ marginTop: 40, paddingTop: 24, borderTop: "1px solid var(--line)" }}>
      <h2 className="n-panel-title">{t.findingsTitle}</h2>
      <div className="n-grid cols-3">
        {GROUPS.map((g) => (
          <section key={g} aria-label={t.groups[g]} className="n-card">
            <h3>{t.groups[g]}</h3>
            <p className="n-muted">{t.groupHelp[g]}</p>
            {all.filter((f) => f.group === g).map((f) => (
              <div key={f.measure}>
                <strong>{f.restricted ? t.restricted : f.name}</strong>
                {f.reasons.map((x) => (
                  <div key={x} className="n-muted">{plainText(x)}</div>
                ))}
                {f.pain_points.length ? <div className="n-muted">{t.painPoints + f.pain_points.map((p) => p.title).join(", ")}</div> : null}
                {f.levers.length ? <div className="n-muted">{t.levers + f.levers.map((p) => p.title).join(", ")}</div> : null}
              </div>
            ))}
            {all.every((f) => f.group !== g) ? <p className="n-muted">{t.noneInGroup}</p> : null}
          </section>
        ))}
      </div>
      <h2 className="n-panel-title">{t.risksTitle}</h2>
      <p className="n-muted">{t.risksHelp}</p>
      {data.risks.length ? (
        <>
          {acceptedSummary(data.risks.map((r) => r.text)).map((l) => (
            <p key={l} className="n-muted">{l}</p>
          ))}
          <ul>
            {data.risks.map((r) => (
              <li key={r.id}>{splitAccepted(r.text).text}</li>
            ))}
          </ul>
        </>
      ) : (
        <p className="n-muted">{t.noRisks}</p>
      )}
    </section>
  );
}

/** The trial table, each rule in plain words, and the findings in three columns. Lens does it all; an analyst may mark a rule as checked. */
export default function TrialScreen() {
  const { assessmentId = "" } = useParams();
  const { user } = useSession();
  const canAct = !!user?.roles.some((r) => r === "analyst" || r === "company_admin");
  const canCheck = !!user?.roles.includes("analyst");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState("");
  const detail = useLoad(() => getAssessment(assessmentId), `m3-assessment-${assessmentId}`);
  const [stamp, setStamp] = useState(0);
  const trial = useLoad(async () => ({ trial: await getTrial(assessmentId), findings: await getFindings(assessmentId) }), `m3-trial-${assessmentId}-${stamp}`,
    (d) => !d.trial.run && !d.trial.compiled);

  async function act(fn: () => Promise<unknown>, failed: string) {
    setBusy(true);
    setProblem("");
    try {
      await fn();
      setStamp((n) => n + 1);
    } catch {
      setProblem(failed);
    } finally {
      setBusy(false);
    }
  }
  const run = () => act(async () => { await compileRules(assessmentId); await runTrial(assessmentId); }, t.runFailed);

  return (
    <>
      <PageHead title={t.title} sub={t.sub} eyebrow={m3.eyebrow}
        crumbs={[{ label: "Intent Centre", to: "/centre/intent" }, { label: t.title }]}
        actions={canAct ? <button type="button" className="n-btn" disabled={busy} onClick={run}>{busy ? t.running : t.run}</button> : undefined} />
      {detail.data ? <ConnectSteps assessmentId={assessmentId} steps={detail.data.steps} /> : null}
      {problem ? <p role="alert" className="state state-error">{problem}</p> : null}
      <ScreenState state={trial.state} message={trial.state === "empty" ? t.empty : trial.message} onRetry={trial.retry}>
        {trial.data ? (
          <>
            <Scoreboard trial={trial.data.trial} />
            <TrialTable rows={trial.data.trial.measures} canCheck={canCheck} onCheck={(m) => act(() => checkRule(assessmentId, m), t.checkFailed)} />
            <FindingsColumns data={trial.data.findings} />
          </>
        ) : null}
      </ScreenState>
      {detail.data ? <NiraNext steps={detail.data.steps} /> : null}
    </>
  );
}
