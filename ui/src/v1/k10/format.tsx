import { useState, type ReactNode } from "react";

import { ApiError } from "../../api/client";
import { Pill, type PillTone } from "../../design";
import type { Where } from "./api";

// K10: how figures read on screen. Every figure arrives from the server; this file only formats it. A missing figure is never shown as zero.
export const NOT_YET = "Not available yet";
export const num = (v: string | null | undefined): number | null => (v === null || v === undefined || v === "" || Number.isNaN(Number(v)) ? null : Number(v));
export const money = (v: string | null | undefined): string => {
  const n = num(v);
  return n === null ? NOT_YET : Number.isInteger(n) ? n.toLocaleString("en-US") : n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
};
export const signed = (v: string | null | undefined): string => {
  const n = num(v);
  return n === null ? NOT_YET : `${n > 0 ? "+" : n < 0 ? "-" : ""}${money(String(Math.abs(n)))}`;
};
export const pct = (v: string | null | undefined, plus = false): string => {
  const n = num(v);
  return n === null ? NOT_YET : `${plus && n > 0 ? "+" : ""}${n.toFixed(2)}%`;
};
export const pts = (v: string | null | undefined): string => {
  const n = num(v);
  return n === null ? NOT_YET : `${n > 0 ? "+" : ""}${n.toFixed(2)}`;
};
export const compact = (v: string | null | undefined, ccy = ""): string => {
  const n = num(v);
  return n === null ? NOT_YET : `${ccy} ${new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 2 }).format(n)}`.trim();
};
export const level = (v: string | null | undefined): string => {
  const n = num(v);
  return n === null ? NOT_YET : n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 4 });
};
export const word = (s: string | null | undefined) => (s ? s.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase()) : "");
export const plain = (e: unknown) => (e instanceof ApiError && e.message ? e.message : "This could not be loaded. Please try again.");

export function tone(s: string | null | undefined): PillTone {
  const w = (s ?? "").toLowerCase();
  if (/^(official|certified|covered|fully explained|signed|live)/.test(w)) return "ok";
  if (/^(stale|late|short|unverified|some unexplained|not certified)/.test(w)) return "late";
  if (/^(revised)/.test(w)) return "open";
  return "draft";
}
export const Status = ({ s }: { s: string | null | undefined }) => (s ? <Pill tone={tone(s)}>{s}</Pill> : null);
export const Outside = ({ children }: { children?: ReactNode }) => <span className="ds-muted" style={{ fontSize: "0.85rem" }}><Pill tone="draft">Outside</Pill> {children}</span>;

/** "Where is this from?" under a figure: opens the plain explanation. */
export function WhereLink({ label, where, id }: { label: string; where?: Where | { text: string }; id?: string }) {
  const [open, setOpen] = useState(false);
  if (!where) return null;
  return (
    <>
      <button type="button" className="ds-link" aria-expanded={open} aria-label={`${label}: Where is this from?`} onClick={() => setOpen(!open)}>Where is this from?</button>
      {open ? <p className="ds-muted" style={{ fontSize: "0.85rem", margin: "4px 0" }} data-trail-id={id}>{where.text}</p> : null}
    </>
  );
}

/** One figure: label, big value, a note line, a status word and where it is from. */
export function Figure({ label, value, note, status, where, id, unavailable }: { label: string; value: string; note?: string | null; status?: string | null; where?: Where; id?: string; unavailable?: string | null }) {
  return (
    <article className="ds-card" aria-label={label} style={{ padding: 16, minWidth: 0 }}>
      <div className="ds-muted" style={{ fontSize: "0.85rem" }}>{label}</div>
      <div className={unavailable ? "ds-muted" : undefined} style={{ fontSize: unavailable ? "1.1rem" : "1.75rem", fontWeight: 600, lineHeight: 1.2, overflowWrap: "anywhere" }}>{unavailable ? NOT_YET : value}</div>
      <div className="ds-muted" style={{ fontSize: "0.85rem", margin: "4px 0" }}>{unavailable || note}</div>
      {!unavailable ? <Status s={status} /> : null}
      <div><WhereLink label={label} where={where} id={id} /></div>
    </article>
  );
}

export const Grid = ({ children }: { children: ReactNode }) => (
  <div style={{ display: "grid", gap: 12, gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 210px), 1fr))" }}>{children}</div>
);
export const Loading = ({ what }: { what: string }) => <p className="ds-muted" role="status">Opening {what}.</p>;
