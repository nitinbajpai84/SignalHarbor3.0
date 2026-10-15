import { m3Intake as T } from "./copy";
import type { AskedTable } from "./api";

/** What we need from a source: one row per column, why, and for which measure. */
export default function AskedTables({ tables }: { tables: AskedTable[] }) {
  return (
    <div className="n-table-wrap">
      <table className="n-table">
        <thead>
          <tr>
            <th scope="col">{T.table}</th>
            <th scope="col">{T.column}</th>
            <th scope="col">{T.why}</th>
            <th scope="col">{T.measure}</th>
          </tr>
        </thead>
        <tbody>
          {tables.flatMap((t) =>
            t.columns.length === 0
              ? [
                  <tr key={t.table_id}>
                    <td>{t.name}</td>
                    <td colSpan={3} className="n-muted">
                      {t.row_means ?? ""}
                    </td>
                  </tr>,
                ]
              : t.columns.map((c, i) => (
                  <tr key={c.field_id}>
                    <td>{i === 0 ? t.name : ""}</td>
                    <td>{c.name}</td>
                    <td>{c.meaning ?? ""}</td>
                    <td>{c.measures.map((m) => m.name).join(", ")}</td>
                  </tr>
                )),
          )}
        </tbody>
      </table>
    </div>
  );
}
