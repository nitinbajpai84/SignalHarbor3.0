import type { CatRow, CatTab, CatTabSchema, GovColumns } from "../api";
import { cellOf, cellText } from "../api";
import { m2Gov as t } from "../copy";

/** The catalogue's Fields and KPIs tabs show the three governance columns beside the rows: personal data, sensitive, who may see it.
 * Read only, and only for the rows the person may see (the server leaves the others out). */
export default function GovernanceColumns({ tab, schema, rows, governance }: { tab: CatTab; schema: CatTabSchema; rows: CatRow[]; governance?: GovColumns }) {
  if (!governance || (tab !== "fields" && tab !== "kpis")) return null;
  const mine = governance[tab];
  const shown = rows.filter((r) => !r._hidden);
  if (shown.length === 0) return null;
  const name = tab === "fields" ? "Field name as in the source" : "KPI name";
  return (
    <div>
      <h3>{t.columnsTitle}</h3>
      <p className="n-muted">{t.columnsHelp}</p>
      <table className="n-table" aria-label={t.columnsTitle}>
        <thead>
          <tr>
            <th>{t.cols.name}</th>
            <th>{t.cols.personal}</th>
            <th>{t.cols.sensitive}</th>
            <th>{t.cols.who}</th>
          </tr>
        </thead>
        <tbody>
          {shown.map((r) => {
            const id = cellText(cellOf(r, schema.id_header));
            const g = mine[id];
            return (
              <tr key={id}>
                <td>{cellText(cellOf(r, name)) || id}</td>
                <td>{g?.personal ?? t.notDecided}</td>
                <td>{g?.sensitive ?? ""}</td>
                <td>{g?.who ?? ""}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
