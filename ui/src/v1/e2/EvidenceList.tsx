import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { PageFrame, Pill } from "../../design";
import { listDocuments, type DocRow } from "./api";

// E2d: manager statements on file.
export default function EvidenceList() {
  const [rows, setRows] = useState<DocRow[] | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { listDocuments().then((r) => setRows(r.documents)).catch(() => setError("The statements could not be loaded. Please try again.")); }, []);
  return (
    <PageFrame title="Evidence" subline="Manager statements and what we read from them.">
      {error ? <p role="alert">{error}</p> : null}
      {rows === null && !error ? <p className="ds-muted" role="status">Loading the statements.</p> : null}
      {rows?.length === 0 ? <p className="ds-muted">No statements have been received yet.</p> : null}
      {rows?.length ? (
        <table><thead><tr><th>Statement</th><th>Fund</th><th>Valued</th><th>Received</th><th>State</th></tr></thead>
          <tbody>{rows.map((d) => (
            <tr key={d.id}><td><Link className="ds-link" to={`/centre/evidence/${d.id}`}>{d.title}</Link></td><td>{d.instrument_name}</td>
              <td>{d.valuation_date}</td><td>{d.received_at}</td><td><Pill tone={d.label === "Current" ? "signed" : "open"}>{d.label}</Pill></td></tr>))}</tbody></table>
      ) : null}
    </PageFrame>
  );
}
