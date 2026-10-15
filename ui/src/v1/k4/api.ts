// K2: the Office view. Shapes are what sh_platform/v1/k4_office.py sends (money arrives as decimal strings, dates as ISO text).
import { apiGet } from "../../api/client";

export interface Where { text: string; table?: string | null; row_id?: string | null; document_id?: string | null; document_title?: string | null; page?: number | null; line?: number | null }
export interface HoldingLine {
  instrument_id: string; name: string; asset_class?: string | null; data_status?: string; value: string | null; currency: string; native: { amount: string | null; currency: string | null };
  status: string; source: string; where: Where;
}
export interface HoldingPortfolio { portfolio_id: string; portfolio_name: string; currency: string; total: string | null; lines: HoldingLine[]; message: string | null }
export interface HoldingEntity { entity_id: string; entity_name: string; total: string | null; portfolios: HoldingPortfolio[] }
export interface Holdings { currency: string; as_of: string; entities: HoldingEntity[]; total: string | null; partial: boolean; stale_after_days: number }

export interface IssuedLine { line_key: string; label: string; issued: string | null; known_now: string | null; difference: string | null; currency: string | null; status: string; case_id: string | null }
export interface Issued {
  report: { report_version_id: string; name: string; period_end: string; issued_at: string | null } | null; message?: string;
  lines?: IssuedLine[]; banner?: string | null; currency?: string | null; currencies?: string[]; currency_message?: string | null; partial?: boolean;
  brief_link?: string; where?: { text: string };
}

export interface Evidence { label: string; table: string | null; row_id: string | null; text: string }
export interface BridgePart { code: "revisions" | "timing" | "fx" | "unexplained"; label: string; amount: string; plain: string; evidence: Evidence[] }
export interface BridgeItem {
  portfolio_id: string; portfolio_name: string; entity_name: string | null; currency: string; available: boolean; message?: string;
  as_of?: string; nav_date?: string; investment_total?: string; administrator_nav?: string; nav_status?: string; difference?: string; parts?: BridgePart[]; where?: Where;
}
export interface NavBridge { currency: string; as_of: string; partial: boolean; portfolios: BridgeItem[] }

export interface LiquidityItem {
  id: string; kind: "call" | "distribution"; recallable: boolean; fund: string | null; due_date: string; amount: string;
  own_amount: string; own_currency: string; status: string; confirmed: boolean;
}
export interface LiquidityBucket { key: string; label: string; calls: string; distributions: string; cash_after_calls: string | null; items: LiquidityItem[] }
export interface LiquidityEntity {
  entity_id: string; entity_name: string; currency: string; available_cash: string; uncalled: string; problems: string[];
  cash_sources: { position_id: string; position_date: string; status: string; amount: string }[];
  buckets: LiquidityBucket[]; unconfirmed: LiquidityItem[];
}
export interface Liquidity { available: boolean; currency: string; as_of: string; message?: string; entities?: LiquidityEntity[] }

export interface WhyEvidence extends Evidence { document_id?: string | null }
export interface WhyLine { label: string; amount: string; plain: string; evidence: WhyEvidence[] }
export interface WhyPart { code: "price" | "trades" | "revisions" | "fx"; label: string; amount: string; lines: WhyLine[] }
export interface WhyMoved {
  available: boolean; message?: string; currency: string; start: string; end: string; portfolios?: string[];
  start_value?: string; end_value?: string; change?: string; percent?: string | null; parts?: WhyPart[]; largest?: string | null;
}

const q = (currency: string, as_of = "") => `?currency=${encodeURIComponent(currency)}${as_of ? `&as_of=${encodeURIComponent(as_of)}` : ""}`;
export const getHoldings = (c: string) => apiGet<Holdings>(`/api/v1/office/holdings${q(c)}`);
export const getIssued = (c: string) => apiGet<Issued>(`/api/v1/office/issued${q(c)}`);
export const getBridge = (c: string) => apiGet<NavBridge>(`/api/v1/office/nav-bridge${q(c)}`);
export const getLiquidity = (c: string) => apiGet<Liquidity>(`/api/v1/office/liquidity${q(c)}`);

export const getWhyMoved = (c: string, start: string, end: string, book = "liquid", portfolioId = "") =>
  apiGet<WhyMoved>(`/api/v1/office/why-moved?start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}&currency=${encodeURIComponent(c)}${portfolioId ? `&portfolio_id=${encodeURIComponent(portfolioId)}` : book ? `&book=${encodeURIComponent(book)}` : ""}`);

/** The portfolios the person may see, read from the holdings route (hidden ones are not sent). */
export const getPortfolios = () => getHoldings("USD").then((h) => h.entities.flatMap((e) => e.portfolios.map((p) => ({ id: p.portfolio_id, name: p.portfolio_name }))));

/** "USD 10,180,000" or "Not available yet": a missing figure is never shown as zero. */
export const money = (v: string | null | undefined, ccy: string | null | undefined): string => {
  if (v === null || v === undefined) return "Not available yet";
  const n = Number(v);
  return `${ccy ?? ""} ${Number.isNaN(n) ? v : n.toLocaleString("en-US", { maximumFractionDigits: 2 })}`.trim();
};
export const sentence = (w: string) => w.charAt(0).toUpperCase() + w.slice(1);
export const day = (iso: string | null | undefined): string => {
  if (!iso) return "";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : `${d.getUTCDate()} ${d.toLocaleString("en-GB", { month: "short", timeZone: "UTC" })} ${d.getUTCFullYear()}`;
};
