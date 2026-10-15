// E5c: Daily Pulse and CIO Brief. The screens use the small shapes below; this file maps the real E5a/E5b responses into them.
import { apiGet, apiSend } from "../../api/client";

export interface PulseItem {
  id: string; headline: string; status: string; valued: string | null; valued_label?: string; received: string | null; affected: string | null;
  needs_me: boolean; case_id: string | null; link: string | null; action: string | null; kind?: string;
}
export interface PulseList { role: string; roles: string[]; items: PulseItem[] }
export interface BriefLine { key: string; holding: string; issued: string; known_now: string; status: string; changed: boolean; portfolio_id?: string | null }
export interface Brief {
  title: string; issued_on: string; currency: string; currencies: string[]; currency_message: string | null;
  banner: { text: string; case_id: string | null } | null; lines: BriefLine[];
}
export interface Explanation {
  refused?: boolean; reason?: string; review_path?: string;
  answer?: string; evidence?: string[]; sources?: { label: string; href: string | null }[]; caveats?: string[]; next_action?: string; approver?: string;
}

// What the servers send (E5a items(), E5b brief() and explain()).
interface RawCard {
  id: string; headline: string; status_word: string; urgency: string; as_of: string | null; received: string | null; effect: string | null;
  kind: string; link: string | null; action: string | null; exception_id: string | null; action_type?: string;
}
interface RawLine { line_key: string; label: string; issued: string | null; known_now: string | null; difference: string | null; currency: string | null; status: string; case_id: string | null }
interface RawBrief {
  report_name: string; period_end: string; issued_at: string | null; banner: string | null; lines: RawLine[]; open_cases: { id: string }[];
  currency: string | null; currencies: string[]; currency_message: string | null;
}
interface RawEvidence { label: string; value: string | null; currency: string | null; as_of?: string | null; source?: string | null; state: string }
interface RawSource { title: string; document_id: string; page: number | null; line: number | null }
interface RawExplain {
  refused: boolean; reason?: string; review_path?: string; answer?: string; evidence?: RawEvidence[]; sources?: RawSource[];
  caveats?: string[]; next_action?: string; approver?: string;
}

export const day = (iso: string | null | undefined): string | null => {
  if (!iso) return null;
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : `${d.getUTCDate()} ${d.toLocaleString("en-GB", { month: "short", timeZone: "UTC" })} ${d.getUTCFullYear()}`;
};
const money = (v: string | null, ccy: string | null): string => {
  if (v === null || v === undefined) return "Not available yet";
  const n = Number(v);
  return `${ccy ?? ""} ${Number.isNaN(n) ? v : n.toLocaleString("en-US", { maximumFractionDigits: 2 })}`.trim();
};
const sentence = (w: string) => w.charAt(0).toUpperCase() + w.slice(1);
export const roleLabel = (r: string) => (r === "cio" ? "CIO" : sentence(r));

/** K8: one written status word per card kind. Revised and Break come from the server as they are; the others are named by what the card is about. */
export const statusWord = (c: Pick<RawCard, "kind" | "status_word" | "headline" | "action_type">): string => {
  const w = c.status_word ?? "";
  if (w.startsWith("Revised")) return w;
  if (w === "Break") return "Break";
  if (c.kind === "exception" && /^limit breached/i.test(c.headline)) return "Limit";
  if (c.kind === "statement") return "Late";
  if (c.kind === "approval") return "Waiting for you";
  if (c.kind === "build" || c.kind === "share") return "Shared";
  if (c.kind === "refresh" || c.kind === "dashboard") return "Refreshed";
  return w;
};

const pulseItem = (c: RawCard): PulseItem => ({
  id: c.id, headline: c.headline, status: statusWord(c), valued: day(c.as_of), received: day(c.received),
  // a manager revision is a change in the manager-reported valuation; anything else (a break, a late file) is a plain difference
  affected: c.effect && c.kind === "exception"
    ? ((c.status_word ?? "").startsWith("Revised") ? `a change of ${c.effect} in the manager-reported valuation` : statusWord(c) === "Limit" ? `${c.effect} above the signed limit` : `a difference of ${c.effect}`)
    : null,
  valued_label: (c.status_word ?? "").startsWith("Revised") || (c.status_word ?? "").startsWith("Estimated") ? "Valued" : "As of",
  needs_me: c.urgency === "needs_me", case_id: c.kind === "exception" ? c.exception_id : null, link: c.link, action: c.action, kind: c.kind,
});
export const toBrief = (r: RawBrief): Brief => ({
  title: r.report_name, issued_on: day(r.issued_at ?? r.period_end) ?? "", currency: r.currency ?? "", currencies: r.currencies ?? [],
  currency_message: r.currency_message ?? null,
  banner: r.banner ? { text: r.banner, case_id: r.lines.find((l) => l.case_id)?.case_id ?? r.open_cases[0]?.id ?? null } : null,
  lines: r.lines.map((l) => ({
    key: l.line_key, holding: l.label, issued: money(l.issued, l.currency), known_now: money(l.known_now, l.currency), status: sentence(l.status),
    portfolio_id: (l as { portfolio_id?: string | null }).portfolio_id ?? null,
    changed: (l.difference !== null && Number(l.difference) !== 0) || ["revised", "unverified", "stale", "draft"].includes(l.status),
  })),
});
export const toExplanation = (r: RawExplain): Explanation => r.refused ? { refused: true, reason: r.reason, review_path: r.review_path } : ({
  answer: r.answer, caveats: r.caveats, next_action: r.next_action, approver: r.approver,
  evidence: (r.evidence ?? []).map((e) => [sentence(e.label), money(e.value, e.currency), e.as_of ? `as at ${day(e.as_of)}` : "", e.source ? `(${e.source})` : "", `· ${e.state}`]
    .filter(Boolean).join(" ")),
  sources: (r.sources ?? []).map((s) => ({ label: `${s.title}${s.page ? `, page ${s.page}` : ""}`, href: `/centre/evidence/${s.document_id}` })),
});

const rv = (id: string) => `/api/v1/brief/${encodeURIComponent(id)}`;
export const getPulse = (role: string) => apiGet<{ role: string; roles: string[]; items: RawCard[] }>(
  `/api/v1/pulse2/items${role ? `?role=${encodeURIComponent(role)}` : ""}`).then((d) => ({ role: d.role, roles: d.roles, items: d.items.map(pulseItem) }));
export const dismissItem = (id: string, reason: string) => apiSend<unknown>("POST", `/api/v1/pulse2/items/${encodeURIComponent(id)}/dismiss`, { reason });
export const takeCase = (caseId: string) => apiSend<unknown>("POST", `/api/v1/cases/${encodeURIComponent(caseId)}/take`, {});
export const getBrief = (id: string, currency: string) => apiGet<RawBrief>(`${rv(id)}${currency ? `?currency=${encodeURIComponent(currency)}` : ""}`).then(toBrief);
export const explain = (id: string, line_key: string, question = "") => apiSend<RawExplain>("POST", `${rv(id)}/explain`, { line_key, question }).then(toExplanation);
