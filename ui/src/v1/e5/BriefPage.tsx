import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { ApiError, apiGet } from "../../api/client";
import { Button, Chip, PageFrame, Pill } from "../../design";
import Comments from "../n2/Comments";
import { explain, toBrief, type Brief, type Explanation } from "./api";
import { statusTone } from "./TodayPage";

// E5c: /centre/brief/:reportVersionId, the CIO Brief. Figures arrive formatted with currency from the server; nothing is computed here.
const plain = (err: unknown) => (err instanceof ApiError && err.message ? err.message : "That did not go through. Please try again.");

type Raw = Parameters<typeof toBrief>[0];
type Timed = Brief & { issued_at: string | null; cutoff_at: string | null };

/** "3 Oct 2026, 18:30 (UTC+08:00)": the date, time and offset exactly as the server stamped them, with no conversion. */
const stamp = (iso: string | null | undefined): string => {
  const m = /^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}:\d{2})(?::[\d.]+)?(Z|[+-]\d{2}:?\d{2})?/.exec(iso ?? "");
  if (!m) return iso ?? "";
  const month = new Date(Date.UTC(2000, Number(m[2]) - 1, 1)).toLocaleString("en-GB", { month: "short", timeZone: "UTC" });
  const off = !m[5] || m[5] === "Z" ? "UTC" : `UTC${m[5].length === 5 ? `${m[5].slice(0, 3)}:${m[5].slice(3)}` : m[5]}`;
  return `${Number(m[3])} ${month} ${m[1]}, ${m[4]} (${off})`;
};

export default function BriefPage() {
  const { reportVersionId = "" } = useParams();
  const [currency, setCurrency] = useState("");
  const [brief, setBrief] = useState<Timed | null>(null);
  const [error, setError] = useState("");
  const [asked, setAsked] = useState<string | null>(null);
  const [answer, setAnswer] = useState<Explanation | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setError("");
    apiGet<Raw & { cutoff_at: string | null }>(`/api/v1/brief/${encodeURIComponent(reportVersionId)}${currency ? `?currency=${encodeURIComponent(currency)}` : ""}`)
      .then((r) => setBrief({ ...toBrief(r), issued_at: r.issued_at, cutoff_at: r.cutoff_at }))
      .catch((e) => setError(plain(e)));
  }, [reportVersionId, currency]);

  async function why(key: string, holding: string) {
    setAsked(holding); setAnswer(null); setBusy(true); setError("");
    try { setAnswer(await explain(reportVersionId, key)); } catch (e) { setError(plain(e)); } finally { setBusy(false); }
  }

  return (
    <PageFrame title={brief?.title ?? "CIO Brief"} subline={brief ? `Issued ${brief.issued_at ? stamp(brief.issued_at) : brief.issued_on}${brief.cutoff_at ? ` · Data cutoff ${stamp(brief.cutoff_at)}` : ""}` : undefined}
      actions={brief && brief.currencies.length > 1 ? <div role="group" aria-label="Currency" style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <span className="ds-muted">Show in</span>
        {brief.currencies.map((c) => <Chip key={c} tone={c === (currency || brief.currency) ? "active" : "default"} onClick={() => setCurrency(c)}>{c}</Chip>)}</div> : undefined}>
      {error ? <p role="alert">{error}</p> : null}
      {brief?.currency_message ? <p className="ds-muted" role="status">{brief.currency_message}</p> : null}
      {brief?.banner ? (
        <p role="status" className="ds-card" style={{ padding: 12 }}>
          {brief.banner.text}{" "}
          {brief.banner.case_id ? <Link className="ds-link" to={`/centre/desk/${brief.banner.case_id}`}>Open the case</Link> : null}
        </p>) : null}
      {!brief && !error ? <p className="ds-muted" role="status">Loading the brief.</p> : null}
      {brief ? (
        <div style={{ overflowX: "auto" }}><table className="ds-table" style={{ width: "100%" }}>
          <thead><tr><th>Holding</th><th>Issued {brief.issued_on}</th><th>Known now</th><th>Status</th><th /></tr></thead>
          <tbody>{brief.lines.map((l) => (
            <tr key={l.key}>
              <td>{l.holding}</td><td>{l.issued}</td><td>{l.known_now}</td>
              <td><Pill tone={statusTone(l.status)}>{l.status}</Pill></td>
              <td>{l.changed ? <Button onClick={() => void why(l.key, l.holding)}>Why did this move?</Button> : null}<Comments eager target={{ kind: "brief_line", id: `${l.portfolio_id ?? "company"}/${l.key}` }} /></td>
            </tr>))}</tbody>
        </table></div>) : null}
      {asked ? (
        <section className="ds-card" style={{ padding: 16, marginTop: 16 }} aria-label="Explanation">
          <h2 style={{ fontSize: "1rem", marginTop: 0 }}>Why did {asked} move?</h2>
          {busy ? <p className="ds-muted" role="status">Working it out.</p> : null}
          {answer?.refused ? <p>{answer.reason} {answer.review_path}</p> : null}
          {answer && !answer.refused ? (
            <>
              <p>{answer.answer}</p>
              {answer.evidence?.length ? <ul>{answer.evidence.map((e, n) => <li key={n}>{e}</li>)}</ul> : null}
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }} aria-label="Sources">
                {(answer.sources ?? []).map((s, n) => <Chip key={n} href={s.href ?? undefined}>{s.label}</Chip>)}
              </div>
              {answer.caveats?.length ? <p className="ds-muted">Caveats: {answer.caveats.join(" ")}</p> : null}
              {answer.next_action ? <p>Next: {answer.next_action}{answer.approver ? ` Approver: ${answer.approver}.` : ""}</p> : null}
            </>) : null}
        </section>) : null}
    </PageFrame>
  );
}
