import StatusPill, { type PillTone } from "../../../components/StatusPill";
import { m3Intake as T } from "./copy";
import type { Profile } from "./api";

const TONE: Record<string, PillTone> = { file_not_arrived: "danger", missing_column: "danger", half_empty: "warning", some_empty: "info", period_short: "warning" };

/** What arrived for one source: each file's columns (type, how full, match) and the gap list. A restricted column shows only its placeholder. */
export default function ProfileView({ profile }: { profile: Profile }) {
  return (
    <div>
      <h4>{T.profile}</h4>
      {profile.tables.map((t) => (
        <div key={t.file}>
          <p>
            <strong>{t.name ?? t.file}</strong> · {T.rows(t.row_count)}
            {t.date_range ? ` · ${T.dates(t.date_range.from, t.date_range.to)}` : ""}
            {t.duplicate_key && t.duplicate_key.duplicates > 0 ? ` · ${T.repeats(t.duplicate_key.duplicates)}` : ""}
          </p>
          <div className="n-table-wrap">
            <table className="n-table">
              <thead>
                <tr>
                  <th scope="col">{T.found}</th>
                  <th scope="col">{T.type}</th>
                  <th scope="col">{T.full}</th>
                  <th scope="col">{T.matched}</th>
                </tr>
              </thead>
              <tbody>
                {t.columns.map((c, i) =>
                  c.restricted ? (
                    <tr key={i}>
                      <td colSpan={4} className="n-muted">
                        {T.restricted}
                      </td>
                    </tr>
                  ) : (
                    <tr key={c.name}>
                      <td>{c.name}</td>
                      <td>{c.type}</td>
                      <td>{Math.round((c.fill ?? 0) * 100)}%</td>
                      <td>{c.match ? <StatusPill tone={c.match.confidence === "high" ? "success" : "info"}>{T.conf[c.match.confidence]}</StatusPill> : <span className="n-muted">{T.noMatch}</span>}</td>
                    </tr>
                  ),
                )}
              </tbody>
            </table>
          </div>
        </div>
      ))}
      <h4>{T.gaps}</h4>
      {profile.gaps.length === 0 ? (
        <p className="n-muted">{T.noGaps}</p>
      ) : (
        <ul className="m1-list">
          {profile.gaps.map((g, i) => (
            <li key={i}>
              <StatusPill tone={TONE[g.kind] ?? "muted"}>{T.gapKind[g.kind]}</StatusPill> {g.text}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
