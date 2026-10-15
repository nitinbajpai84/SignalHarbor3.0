import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError } from "../../api/client";
import { PageFrame, Pill } from "../../design";
import { byMaterialityThenDue, listCases, MATERIALITY_NAMES, type Case, type CaseRow } from "./api";

// E4c: /centre/desk. Cases ordered by materiality, then due time.
export const money = (n?: number | null, ccy?: string | null) => (n == null ? "" : `${ccy ?? ""} ${n.toLocaleString("en-GB")}`.trim());
export const dueText = (d: string | null) => (d ? `Due ${new Date(d).toLocaleDateString("en-GB", { day: "numeric", month: "short" })}` : "No due date");

/** What kind of case this is, in words (exception_type from the server). Unknown kinds show no word rather than a code. */
const KINDS: Record<string, string> = { policy_question: "Policy question", limit_breach: "Limit breach", break: "Difference", capital_call: "Capital call",
  revision: "Valuation difference", comment: "Raised from a comment" };
export const kindName = (t?: string | null) => (t ? KINDS[t] ?? "" : "");

export default function CasesPage({ framed = false }: { framed?: boolean }) {
  const [rows, setRows] = useState<CaseRow[] | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    listCases().then((r) => setRows([...r.cases].sort(byMaterialityThenDue)))
      .catch((e) => { setRows([]); setError(e instanceof ApiError && e.message ? e.message : "The cases could not be loaded."); });
  }, []);
  const body = (
    <>
      {error ? <p role="alert">{error}</p> : null}
      {rows === null ? <p className="ds-muted" role="status">Loading the cases.</p>
        : rows.length === 0 && !error ? <p className="ds-muted">No open cases.</p>
        : <div className="ds-table-wrap"><table className="ds-table"><thead><tr><th>Case</th><th>Kind</th><th>What</th><th>Size</th><th>Materiality</th><th>Due</th></tr></thead>
          <tbody>{rows.map((r) => (
            <tr key={r.id}>
              <td><Link className="ds-link" to={`/centre/desk/${encodeURIComponent(r.id)}`}>{r.number}</Link></td>
              <td>{kindName((r as Case).exception_type)}</td><td>{r.title}</td><td>{money(r.amount, r.currency)}</td>
              <td><Pill tone={r.materiality === "high" ? "late" : "open"}>{MATERIALITY_NAMES[r.materiality]}</Pill></td>
              <td>{dueText(r.due)}</td>
            </tr>))}</tbody></table></div>}
    </>
  );
  return framed ? body : <PageFrame title="Action Desk" subline="Cases that need a person, biggest first.">{body}</PageFrame>;
}
