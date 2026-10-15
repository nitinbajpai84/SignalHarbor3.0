// K10: the Consume reading room. Shapes are what sh_platform/v1/k10_note.py sends (money and percentages arrive as decimal strings, dates as ISO text).
import { apiGet, apiSend } from "../../api/client";

export interface Where { text: string; sources?: { text: string | null }[] }
export interface Tile {
  key: string; label: string; available: boolean; value: string | null; kind: "money" | "change" | "percent" | "points" | "count"; currency?: string; note?: string | null; status?: string | null;
  trail_id?: string; where?: Where;
}
export interface Moved { label: string; detail: string; amount: string | null; status: string | null; trail_id: string; case_id?: string | null; unconfirmed?: boolean }
export interface CaseItem { number: string; title: string; kind: string; limit: boolean; material: boolean; href: string }
export interface MarketLine { name: string; kind: string; level: string; month_change_pct: string | null; day_change_pct: string | null; outside: boolean; trail_id: string }
export interface Note {
  currency: string; as_of: string; period_end: string; company: string; dateline: string; headline: string; short: string; summary: string | null;
  tiles: Tile[]; moved: Moved[]; watch: { text: string; trail_id: string; href?: string }[];
  needs_you: { count: number; items: CaseItem[]; href: string };
  markets: MarketLine[]; reports: { name: string; state: string; version: number | null; link: string | null }[];
  built: { text: string; report: string | null }; comment_target: { kind: "brief_line"; id: string };
}

/** The Today page (GET /consume/today): one sentence, four key numbers, what moved, the markets in a line. */
export interface Today {
  currency: string; as_of: string; period_end: string; dateline: string; headline: string; tiles: Tile[]; moved: Moved[]; built: string; comment_target: { kind: "brief_line"; id: string };
  markets: { text: string; month: string; sources: { label: string | null; tag: Tag | null; date: string }[] } | null;
}
export type Tag = "FILE" | "LIVE API";
export interface Trust { status: string; detail: string | null }
export interface HealthRow {
  portfolio_id: string; portfolio: string; entity: string; value: string | null; pnl: string | null; return_pct: string | null; ahead_pts: string | null; benchmark_label: string | null;
  trust: Trust; message: string | null; trail_id: string; where: { text: string };
}
export interface HealthEntity { entity_id: string; entity: string; portfolios: number; value: string | null; pnl: string | null; trust: Trust; trail_id: string; where: { text: string } }
/** GET /consume/health: the portfolios and entities with value, month P&L, return and trust; the fund league has its own call. */
export interface Health {
  currency: string; as_of: string; period: { start: string; end: string; month: string }; portfolios: HealthRow[]; entities: HealthEntity[];
  total: { value: string | null; pnl: string | null; count: number; unexplained: string | null };
  funds: { official: number; revised: number; estimated: number; old: number; total: number; estimated_who: string; old_who: string };
}

export interface BridgeRow { portfolio: string; entity: string | null; administrator: string | null; ours: string | null; difference: string | null; available: boolean; nav_date?: string; why: string; trail_id: string; where?: { text: string } }
export interface IssuedLine { line_key: string; label: string; issued: string | null; known_now: string | null; difference: string | null; currency: string | null; status: string }
export interface Pnl {
  currency: string; as_of: string; other_currency: string; total: string | null; partial: boolean;
  issued: { report: { name: string; period_end: string; issued_at: string | null; when?: string } | null; lines?: IssuedLine[]; banner?: string | null; message?: string; brief_link?: string };
  other_total: { issued: string | null; known_now: string | null } | null; rate: { pair: string; date: string; rate: string } | null;
  liquid_book: {
    day: { available: boolean; message: string };
    month: { label: string; change: string | null; percent: string | null; available: boolean; message: string | null; movers: { name: string; amount: string; plain: string }[]; where?: Where };
    ytd: { available: boolean; percent: string | null; message: string };
  };
  bridge: BridgeRow[]; bridge_total: { administrator: string; ours: string; difference: string } | null; by_entity: { entity_id: string; name: string; value: string | null; trail_id: string }[];
}

export type Period = "month" | "ytd" | "inception";
export interface Change { start: string; end: string; start_level: string | null; end_level: string | null; change_pct: string | null; change_abs?: string | null }
export interface Provenance { label: string | null; tag: Tag | null; date: string | null; demo: boolean }
export interface IndexRow {
  series_key: string; name: string; kind: "index" | "fx" | "yield" | "macro" | "proxy" | "placeholder"; outside: boolean; source: string | null; latest: { date: string; level: string } | null; provenance?: Provenance | null;
  periods: Record<Period, Change>; direction: string | null; trail_id: string; where: { text: string }; message?: string;
}
export interface PortfolioRow { portfolio: string; entity: string | null; benchmark_label: string | null; return_pct: string | null; benchmark_pct: string | null; ahead_pts: string | null; status: string | null; message: string | null; trail_id: string; where: { text: string } }
export interface FundRow {
  fund_id: string; fund: string; manager: string; manager_id: string; value: string | null; currency: string | null; valuation_date: string | null; status: string; status_key: string; note: string;
  compared_with: string | null; index_signed?: boolean; index_return: string | null; fund_return: string | null; alpha: string | null; message: string; trail_id: string; where: { text: string }; rank?: number;
}
export interface Headline { title: string; source: string; date: string | null; tag: Tag; outside: boolean; trail_id: string }
export interface NewsItem { manager: string; source: string; title: string; date: string; text: string | null; locked: boolean; outside: boolean; href: string; trail_id: string }
export interface Signals {
  currency: string; as_of: string; period: Period; period_start: string; period_end: string; refreshed: string; indexes: IndexRow[]; portfolios: PortfolioRow[];
  benchmark_note: string | null; funds: FundRow[]; read: string | null; news: NewsItem[]; headlines: Headline[]; outside_note: string;
}
export interface League {
  as_of: string; period_end: string; funds: FundRow[]; managers: number; rank: "alpha" | "value";
  summary: { official: number; revised: number; estimated: number; old: number; total: number; ahead: number | null; ahead_note: string | null };
  worst: { fund: string; text: string; href: string } | null; note: string;
}

export interface ReportVersion { id: string; number: number; status: string; state: string; period_end: string | null; issued_at: string | null; signed_by: string | null; link: string; pdf: string | null; pptx?: string | null }
export interface ReportRow {
  id: string; name: string; summary: string; state: string; live: boolean; version: number | null; signed_by: string | null; signed_at: string | null;
  link: string | null; pdf: string | null; pptx?: string | null; versions: ReportVersion[];
}
export interface Library { reports: ReportRow[]; waiting: number; pdf_available: boolean; pptx_available?: boolean; delivery: { text: string; href: string; action: string }[] }
export interface EmailNote { subject: string; html: string; text: string }

const q = (c: string, extra = "") => `currency=${encodeURIComponent(c)}${extra}`;
export const getToday = (c: string) => apiGet<Today>(`/api/v1/consume/today?${q(c)}`);
export const getHealth = (c: string) => apiGet<Health>(`/api/v1/consume/health?${q(c)}`);
export const getNote = (c: string) => apiGet<Note>(`/api/v1/consume/note?${q(c)}`);
export const getPnl = (c: string) => apiGet<Pnl>(`/api/v1/consume/pnl?${q(c)}`);
export const getSignals = (c: string, period: Period) => apiGet<Signals>(`/api/v1/consume/signals?${q(c, `&period=${period}`)}`);
export const getLeague = (rank: "alpha" | "value") => apiGet<League>(`/api/v1/consume/league?rank=${rank}`);
/** V6: the signed fund-to-index mapping. `series_key` is the signed index, `proposed_series_key` what the head of data starts from; only the head of data seat signs. */
export interface IndexMap {
  signed: boolean; signed_by: string | null; signed_at: string | null; version: number; can_sign: boolean;
  funds: { fund_id: string; fund: string; series_key: string | null; proposed_series_key: string | null }[]; choices: { series_key: string; name: string }[];
}
export const getIndexMap = () => apiGet<IndexMap>("/api/v1/consume/index-map");
export const signIndexMap = (rows: Record<string, string>) => apiSend<IndexMap>("POST", "/api/v1/consume/index-map", { rows });
export const getLibrary = () => apiGet<Library>("/api/v1/consume/reports");
/** V5W-4 (Delivery step): the Morning Note sections that approved, live channels add. A server without that route gives none. */
export const getSections = () => apiGet<{ lines: { title: string; lines: string[] }[] }>("/api/v1/consume/delivery-lines").then((r) => r.lines, () => []);
export const getEmail = (c: string) => apiGet<EmailNote>(`/api/v1/consume/email-note?${q(c)}`);
