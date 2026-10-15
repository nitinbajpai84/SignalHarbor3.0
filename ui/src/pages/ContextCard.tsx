import { useEffect, useState, type ReactNode } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { Button, Pill, SideCard, type PillTone } from "../design";
import { apiSend } from "../api/client";
import { LENS_NAMES, slug } from "./consumeLens";

// Context card of a gold table (spec 60 Screen C). Drafted by the Architect and Lens; only the data owner confirms, corrects or disputes it.
// The server says who may act (`can_act`); this file never works out a role.

export interface CardLine { text: string | null; mark?: "guessed" | "stated"; from?: string | null; title?: string }
type LineKey = "meaning" | "lineage" | "owner" | "rules" | "last_change";
export interface ContextCardData {
  table: string; state: "draft" | "confirmed" | "changed" | "disputed" | null; empty?: string; restricted?: string; owner?: string | null;
  lines?: Partial<Record<LineKey, CardLine>>; measures?: { code: string; name: string | null; restricted: boolean }[];
  made_by?: { how: "created" | "changed"; title: string | null; href: string | null; text: string | null } | null;
  lineage_href?: string; suggest_href?: string; drafted_line?: string; dispute?: { by?: string; reason?: string } | null;
  can?: { confirm: boolean; edit: boolean; dispute: boolean };
}
export interface MeasureLens { key: string; mark?: "guessed" | "stated" | null }

const STATE: Record<string, { label: string; tone: PillTone }> = {
  draft: { label: "Draft", tone: "draft" }, confirmed: { label: "Confirmed", tone: "ok" },
  changed: { label: "Changed since confirmed", tone: "late" }, disputed: { label: "Disputed", tone: "failed" },
};
const NA = "Not available yet";
const LINES: [LineKey, string, string][] = [
  ["meaning", "What it means", `${NA}: no signed definition`],
  ["lineage", "Where it comes from", "Not on the map yet"],
  ["owner", "Owner", `${NA}: no data owner named`],
  ["rules", "Quality rules", "No quality rule set yet"],
  ["last_change", "Last change and why", "No change recorded since it was built"],
];

export function LensChip({ lens }: { lens?: MeasureLens | null }) {
  if (!lens) return <Pill tone="draft">No view yet</Pill>;
  return <Link to={`/centre/consume/lens/${slug(lens.key)}`}><Pill tone="draft">{LENS_NAMES[lens.key] ?? lens.key}{lens.mark === "stated" ? "" : " (Lens draft)"}</Pill></Link>;
}

export function ContextCard({ card, onChanged }: { card: ContextCardData | null | undefined; onChanged: (c: ContextCardData) => void }) {
  const [sp] = useSearchParams();
  const [open, setOpen] = useState(() => typeof window === "undefined" || window.innerWidth >= 720 || sp.get("card") === "confirm");
  const [edit, setEdit] = useState<string | null>(null), [text, setText] = useState(""), [why, setWhy] = useState("");
  const [reason, setReason] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { setErr(null); }, [card?.state]);

  if (!card || !card.state) {
    return (
      <SideCard title="Context card">
        <p>{card?.restricted ?? card?.empty ?? "No context card yet. The Architect drafts one when the blueprint that builds this table is signed."}</p>
        {card?.restricted && card.owner ? <p>Data owner: {card.owner}</p> : null}
      </SideCard>
    );
  }
  const can = card.can;
  const base = `/api/company/consume/cards/${encodeURIComponent(card.table.replace(/^gold\./, ""))}`;
  const act = (path: string, body: object) =>
    apiSend<ContextCardData>("POST", `${base}/${path}`, body).then((c) => { setEdit(null); setReason(null); setWhy(""); onChanged(c); })
      .catch(() => setErr("That was not saved. Please try again."));
  const st = STATE[card.state] ?? STATE.draft!;
  const row = (label: string, body: ReactNode) => <div key={label}><dt className="ds-muted">{label}</dt><dd>{body}</dd></div>;
  return (
    <SideCard title="Context card">
      <p><button type="button" className="ds-chip" aria-expanded={open} onClick={() => setOpen(!open)}>{open ? "Hide" : "Show"}</button>{" "}
        <strong>{card.table}</strong> <Pill tone={st.tone}>{st.label}</Pill></p>
      {open ? <>
        <dl className="ds-soft">
          {LINES.map(([k, label, empty]) => {
            const l = card.lines?.[k];
            if (edit === k) {
              return row(label, <>
                <textarea aria-label={`Correct ${label}`} rows={3} value={text} onChange={(e) => setText(e.target.value)} />
                <input aria-label="Why" placeholder="Why this line changes" value={why} onChange={(e) => setWhy(e.target.value)} />
                <Button variant="primary" disabled={!text.trim() || !why.trim()} onClick={() => act("edit", { line: k, text, why })}>Save the line</Button>{" "}
                <Button onClick={() => setEdit(null)}>Cancel</Button>
              </>);
            }
            return row(label, <>
              {l?.text ?? empty}
              {l?.text && l.mark === "guessed" ? <span className="ds-muted"> (draft)</span> : null}
              {can?.edit && l?.text ? <>{" "}<button type="button" className="ds-chip" onClick={() => { setEdit(k); setText(l.text ?? ""); }}>Correct a line</button></> : null}
            </>);
          })}
          {row("Measures it serves", card.measures?.length
            ? card.measures.map((m) => <span key={m.code}>{m.restricted ? "A restricted measure" : <Link to={`/centre/consume/feeds/${encodeURIComponent(m.code)}`}>{m.name}</Link>}{" "}</span>)
            : "Serves no governed measure yet")}
          {row("Made or changed by", card.made_by
            ? (card.made_by.href && card.made_by.title ? <>{card.made_by.how === "created" ? "Created by " : "Changed by "}<Link to={card.made_by.href}>{card.made_by.title}</Link></> : card.made_by.text ?? "An Initiative you cannot open")
            : `${NA}: built before Initiatives were recorded`)}
        </dl>
        {card.lineage_href ? <p><Link to={card.lineage_href}>Show lineage</Link></p> : null}
        <p className="ds-muted">{card.drafted_line}{card.state === "draft" || card.state === "changed" ? " Not confirmed yet." : ""}</p>
        {card.dispute?.reason ? <p className="ds-warn">Disputed: {card.dispute.reason}</p> : null}
        {can?.confirm ? (reason === null ? <>
          <Button variant="primary" disabled={card.state === "confirmed"} onClick={() => act("confirm", {})}>Confirm this card</Button>{" "}
          <Button onClick={() => setReason("")}>This is wrong</Button>
        </> : <>
          <input aria-label="Reason" placeholder="What is wrong, in a sentence" value={reason} onChange={(e) => setReason(e.target.value)} />
          <Button variant="primary" disabled={!reason.trim()} onClick={() => act("dispute", { reason })}>Send it back to the Architect</Button>{" "}
          <Button onClick={() => setReason(null)}>Cancel</Button>
        </>) : null}
        {err ? <p role="alert" className="ds-warn">{err}</p> : null}
        {card.suggest_href ? <p><Link to={card.suggest_href}>Suggest a change</Link></p> : null}
      </> : null}
    </SideCard>
  );
}
