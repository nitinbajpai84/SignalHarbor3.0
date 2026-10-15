import type { CatRow, CatTab, CatTabSchema, TechColumns } from "../api";
import { cellOf, cellText } from "../api";
import { m2Tech as t } from "./copy";

/** The catalogue's KPIs tab shows each measure's calculation and inputs; the Fields and Extractions tabs show which measures use each row, so the
 * catalogue alone is enough for the next module. Read only, and only for what the person may see (the server leaves the rest out). */
export default function TechnicalColumns({ tab, schema, rows, technical }: { tab: CatTab; schema: CatTabSchema; rows: CatRow[]; technical?: TechColumns }) {
  if (!technical || !["kpis", "fields", "extractions"].includes(tab)) return null;
  const shown = rows.filter((r) => !r._hidden);
  if (shown.length === 0) return null;
  if (tab === "kpis") {
    return (
      <div>
        <h3>{t.cat.title}</h3>
        <p className="n-muted">{t.cat.help}</p>
        <table className="n-table" aria-label={t.cat.title}>
          <thead>
            <tr>
              {(["name", "calculation", "sources", "tables", "fields", "filters", "grain", "period", "currency", "confirmed"] as const).map((c) => <th key={c} scope="col">{t.cat.cols[c]}</th>)}
            </tr>
          </thead>
          <tbody>
            {shown.map((r) => {
              const id = cellText(cellOf(r, schema.id_header));
              const k = technical.kpis[id];
              return (
                <tr key={id}>
                  <th scope="row">{cellText(cellOf(r, "KPI name")) || id}</th>
                  <td style={{ whiteSpace: "pre-wrap" }}>{k?.calculation || t.notAvailable}</td>
                  <td>{k?.sources}</td>
                  <td>{k?.tables}</td>
                  <td>{k?.fields}</td>
                  <td>{k?.filters}</td>
                  <td>{k?.grain}</td>
                  <td>{k?.period}</td>
                  <td>{k?.currency_basis}</td>
                  <td>{k?.confirmed}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    );
  }
  const name = tab === "fields" ? "Field name as in the source" : "What to extract";
  return (
    <div>
      <h3>{t.cat.usedIn}</h3>
      <table className="n-table" aria-label={t.cat.usedIn}>
        <tbody>
          {shown.map((r) => {
            const id = cellText(cellOf(r, schema.id_header));
            const used = technical.inputs[id] ?? [];
            return (
              <tr key={id}>
                <th scope="row">{cellText(cellOf(r, name)) || id}</th>
                <td>{used.length ? used.join(", ") : t.cat.notUsed}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
