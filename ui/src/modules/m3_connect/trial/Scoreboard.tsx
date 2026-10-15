import type { TrialView } from "./api";
import { trialText as t } from "./copy";

interface ScoreboardProps {
  trial: TrialView;
}

export default function Scoreboard({ trial }: ScoreboardProps) {
  const nonRestricted = trial.measures.filter((m) => !m.restricted);
  const matches = nonRestricted.filter((m) => m.result === "matches").length;
  const gaps = nonRestricted.filter((m) => m.result === "gap").length;
  const cannot = nonRestricted.filter((m) => m.result === "cannot").length;
  const restricted = trial.measures.filter((m) => m.restricted).length;

  return (
    <section aria-label={t.scoreboardTitle} style={{ marginBottom: 24 }}>
      <h2 className="n-panel-title">{t.scoreboardTitle}</h2>
      <div className="n-grid cols-3" style={{ marginBottom: 12 }}>
        <div className="n-kpi">
          <div className="label">Match</div>
          <div className="value-row">
            <div className="value">{matches}</div>
          </div>
          <p style={{ margin: 0, fontSize: "12.5px", lineHeight: 1.4 }}>{t.scoreboardMatches}</p>
        </div>
        <div className="n-kpi">
          <div className="label">Gap</div>
          <div className="value-row">
            <div className="value">{gaps}</div>
          </div>
          <p style={{ margin: 0, fontSize: "12.5px", lineHeight: 1.4 }}>{t.scoreboardGap}</p>
        </div>
        <div className="n-kpi">
          <div className="label">Not yet</div>
          <div className="value-row">
            <div className="value">{cannot}</div>
          </div>
          <p style={{ margin: 0, fontSize: "12.5px", lineHeight: 1.4 }}>{t.scoreboardCannotCreate}</p>
        </div>
      </div>
      {restricted > 0 ? (
        <div style={{ fontSize: "13px", color: "var(--text-muted)", display: "flex", gap: "8px", alignItems: "center" }}>
          <span>{t.scoreboardRestricted}</span>
          <span>·</span>
          <span>{restricted} {t.scoreboardRestrictedDetail}</span>
        </div>
      ) : null}
    </section>
  );
}
