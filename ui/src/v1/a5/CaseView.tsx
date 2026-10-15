import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { Button, day } from "../../design";
import { listDocuments, type DocRow } from "../e2/api";
import type { Case } from "../e4/api";
import CasePage from "../e4/CasePage";
import { WhereFrom } from "./TrailHost";

// K8: the case page. "Where is this from?" and the evidence sit inside the page frame (above the history), and a case with no statements behind it
// (a break or a limit breach) shows what was compared instead of an empty evidence list.
type FullCase = Case;
export const NO_STATEMENTS = ["break", "limit_breach", "capital_call"];
const KIND_WORDS: Record<string, string> = { break: "The two records compared", capital_call: "The notice and the commitment it draws on", limit_breach: "The limit and the figures checked against it" };

const SHOWN = 3;
const dated = (d: DocRow) => d.valuation_date || d.received_at || "";
/** "valued 30 Sep 2026" or, for a notice with no valuation date, "received 5 Oct 2026": never a blank date. */
export const docWhen = (d: DocRow) => (d.valuation_date ? `valued ${day(d.valuation_date)}` : d.received_at ? `received ${day(d.received_at)}` : "date not given");

/** The statements of the fund(s) this case is about (the case names them in its title or its "affects" list), not the whole company list.
 * Newest first; the latest three show and the rest are one press away, so old monthly statements do not bury the ones that matter. */
function Statements({ c }: { c: FullCase }) {
  const [rows, setRows] = useState<DocRow[] | null>(null);
  const [all, setAll] = useState(false);
  useEffect(() => {
    listDocuments().then((d) => {
      const hay = [c.title, ...(c.affects ?? [])].join(" ").toLowerCase();
      setRows(d.documents.filter((x) => x.instrument_name && hay.includes(x.instrument_name.toLowerCase())).sort((a, b) => dated(b).localeCompare(dated(a))));
    }).catch(() => setRows([]));
  }, [c]);
  if (rows === null) return <p className="ds-muted" role="status">Loading the statements for this case.</p>;
  if (!rows.length) return <p className="ds-muted">No statements are linked to this case.</p>;
  return <>
    <ul>{(all ? rows : rows.slice(0, SHOWN)).map((d) => <li key={d.id}><Link className="ds-link" to={`/centre/action/evidence/${d.id}`}>{d.title}</Link>{" "}<span className="ds-muted">{docWhen(d)}, {d.label}</span></li>)}</ul>
    {rows.length > SHOWN && !all ? <Button onClick={() => setAll(true)}>Show all {rows.length} documents</Button> : null}
  </>;
}

export default function CaseView() {
  // CasePage reads the case and hands it to this slot, drawn just above the History section (one read, no DOM patching).
  return (
    <CasePage extra={(c: FullCase) => {
      const noStatements = !!c.exception_type && NO_STATEMENTS.includes(c.exception_type);
      return <div style={{ margin: "8px 0" }}>
        {/* the trail looks the case up by its id; the address may carry the number (CASE-0003), so pass the id the server gave (a2.3) */}
        <WhereFrom kind="case" id={c.id} />
        <section aria-label={noStatements ? "What was compared" : "Evidence"}>
          {noStatements ? <>
            <h2>{KIND_WORDS[c.exception_type as string]}</h2>
            <p>{c.description || "The figures behind this case are not available yet."}</p>
          </> : <><h2>Evidence for this case</h2><Statements c={c} /></>}
        </section></div>;
    }} />
  );
}
