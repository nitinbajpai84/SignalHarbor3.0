import ScreenState from "../../components/ScreenState";
import { useLoad } from "../../components/useLoad";
import { getDefinitions } from "./api";
import { day } from "./dates";

// The agreed meaning of each KPI and every variant of it, with the team and project that own each one.
export default function DefinitionsTab({ focus }: { focus: string | null }) {
  const { state, data, message, retry } = useLoad(getDefinitions, "k3-definitions", (d) => d.concepts.length === 0);
  return (
    <ScreenState state={state} message={state === "empty" ? "No measure has been defined yet. Definitions appear here when an intent of work with measures is signed." : message} onRetry={retry}>
      {data?.concepts.map((c) => (
        <section key={c.id} className="ds-card" style={{ padding: 14, marginBottom: 12, outline: focus === c.id || focus === c.name ? "2px solid var(--teal)" : "none" }}>
          <h2 style={{ fontSize: 16, margin: 0 }}>{c.name}</h2>
          {c.difference ? <p className="ds-muted" style={{ margin: "4px 0 8px" }}>{c.difference}</p> : null}
          <ul style={{ margin: 0, paddingLeft: 18 }}>
            {c.variants.map((v) => (
              <li key={v.id} style={{ marginBottom: 6 }}>
                <strong>{v.team ?? "A team"}</strong> in {v.project}
                {v.hidden ? <span className="ds-muted"> (the wording is for the project team)</span>
                  : <> says: {v.definition || "No wording yet"}{v.unit ? ` (${v.unit}${v.period ? `, ${v.period}` : ""})` : ""}
                    <div className="ds-footnote">Owner {v.owner ?? "not named yet"}. Version {v.version ?? 1}. Signed {day(v.signed_on)}.</div></>}
              </li>
            ))}
          </ul>
        </section>
      ))}
    </ScreenState>
  );
}
