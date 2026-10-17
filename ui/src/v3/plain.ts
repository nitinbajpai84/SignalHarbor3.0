import { useEffect, useState } from "react";

import { listThreads } from "./api";

/** 880400.00 -> 880,400.00; leaves short numbers, text and anything already grouped alone. */
export function fmtNum(v: string | number): string {
  return String(v).replace(/(?<![\d.,/:]|\d-)(\d{4,})(\.\d+)?(?![\d,/:]|-\d)/g, (_, i: string, f = "") => i.replace(/\B(?=(\d{3})+$)/g, ",") + f);
}

/** What the office calls a table or column. Anything not listed falls back to Title Case of the snake_case name. */
const LABELS: Record<string, string> = {
  source_system: "Where it came from", legal_entities: "Legal entities", cash_movements: "Cash movements",
  counterparty: "Counterparty", reference: "Reference", amount_usd: "Amount (USD)", called_to_date: "Called to date",
};
export function plainName(raw: string): string {
  const last = raw.split(".").pop() ?? raw;
  return LABELS[last] ?? last.replace(/[_\s]+/g, " ").trim().replace(/^./, (c) => c.toUpperCase());
}

/** A role id in words: ops_lead -> Ops lead, cfo -> CFO. */
export const roleName = (id: string) => plainName(id).replace(/(cfo|coo|cio|ceo)/gi, (m) => m.toUpperCase());

/** Skill names the office reads; the skill id is never touched. */
const SKILL_NAMES: Record<string, string> = { "propose ontology addition": "Suggest a new kind of record" };
export const skillLabel = (name: string) => SKILL_NAMES[name.trim().toLowerCase()] ?? name;
export const noOntology = (s: string) => s.replace(/\bontology\b/gi, "business model");

/** True for machine ids such as run-20261016-225642-9d02 or t-f15adc6b8f. */
export const looksLikeId = (s: string) => /^(run|t)-[\w-]+$/i.test(s.trim()) || /^[a-z]+_[a-z0-9_]+$/.test(s.trim());

/** "9 Oct, 06:11" from an ISO time; text that is not a time comes back as it is, and an id comes back empty. */
export function fmtWhen(started: string): string {
  const d = new Date(started);
  if (Number.isNaN(d.getTime())) return looksLikeId(started) ? "" : started;
  const day = d.toLocaleDateString("en-GB", { day: "numeric", month: "short" });
  const time = d.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", hour12: false });
  return `${day}, ${time}`;
}
export const runLabel = (started: string) => { const w = fmtWhen(started); return w ? `Run on ${w}` : "Run"; };

/** A thread id is real only when it is a non-empty string other than "null". */
export const hasThread = (id: string | null | undefined): id is string => !!id && id !== "null" && id !== "undefined";

/** Thread id -> the use case's title. Unknown ids read "A use case", never the id. */
export function useThreadTitles(): (id: string | null | undefined) => string {
  const [m, setM] = useState<Record<string, string>>({});
  useEffect(() => { listThreads().then((r) => setM(Object.fromEntries((r.threads ?? []).map((t) => [t.id, t.title]))), () => undefined); }, []);
  return (id) => (id && m[id]) || "A use case";
}
