import StatusPill from "../../../components/StatusPill";
import type { Kpi, KpiState } from "../api";
import { m2Work } from "../copy";
import ProvCell from "./ProvCell";

const STATE_TONE: Record<KpiState, "muted" | "warning" | "info" | "success"> = {
  not_started: "muted",
  drafted: "info",
  questions_open: "warning",
  signed: "success",
};

interface Props {
  kpis: Kpi[];
  selected: string | null;
  onSelect: (id: string) => void;
}

/** Slide 4: one row per measure with its four things, each stated, guessed or unknown. A measure the viewer is not named for
 * shows only that it exists. */
export default function TriageTable({ kpis, selected, onSelect }: Props) {
  return (
    <div className="n-table-wrap">
      <table className="n-table">
        <thead>
          <tr>
            <th scope="col">{m2Work.cols.kpi}</th>
            <th scope="col">{m2Work.cols.definition}</th>
            <th scope="col">{m2Work.cols.owner}</th>
            <th scope="col">{m2Work.cols.producer}</th>
            <th scope="col">{m2Work.cols.gathered}</th>
            <th scope="col">{m2Work.cols.state}</th>
            <th scope="col">{m2Work.cols.build}</th>
          </tr>
        </thead>
        <tbody>
          {kpis.map((k) => (
            <tr key={k.id} aria-selected={selected === k.id}>
              <th scope="row">
                {k.restricted ? (
                  k.name
                ) : (
                  <button type="button" className="n-btn sm" aria-label={`${m2Work.details}: ${k.name}`} onClick={() => onSelect(k.id)}>
                    {k.name}
                  </button>
                )}
              </th>
              {k.restricted ? (
                <td colSpan={4}>
                  <StatusPill tone="muted">{m2Work.restricted}</StatusPill> <span className="n-muted">{m2Work.restrictedNote}</span>
                </td>
              ) : (
                <>
                  <td><ProvCell p={k.triage.definition} /></td>
                  <td><ProvCell p={k.triage.owner} /></td>
                  <td><ProvCell p={k.triage.producer} /></td>
                  <td><ProvCell p={k.triage.gathered} /></td>
                </>
              )}
              <td>
                <StatusPill tone={STATE_TONE[k.state]}>{m2Work.states[k.state]}</StatusPill>
              </td>
              <td>{!k.restricted && k.build ? <StatusPill tone={k.build.ready ? "success" : "muted"}>{k.build.label}</StatusPill> : null}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
