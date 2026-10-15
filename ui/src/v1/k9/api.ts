// CS1: the daily key numbers. Shapes are what sh_platform/v1/k9_daily.py sends (money and percentages arrive as decimal strings, dates as ISO text).
import { apiGet } from "../../api/client";

export interface Source { text: string | null; table?: string | null; row_id?: string | null }
export interface Where { text: string; sources?: Source[] }
interface Base { available: boolean; message?: string | null; status?: string; trail_id?: string; where?: Where }
export interface Nav extends Base { currency: string; total: string | null; partial: boolean; by_entity: { entity_id: string; name: string; value: string | null; trail_id: string }[] }
export interface Issued extends Base {
  currency: string; report: string; period_end: string; issued_at: string | null; issued: string | null; known_now: string | null; difference: string | null; banner: string | null; brief_link: string;
}
export interface Period { label: string; start: string; end: string; portfolio: string | null; benchmark: string | null; difference: string | null; certified: boolean; problems: string[]; message: string | null; trail_id: string }
export interface Returns extends Base { portfolio: string; benchmark_code: string; periods: Period[] }
export interface Lever { code: string; label: string; amount: string; trail_id: string }
export interface Mover { name: string; amount: string; trail_id: string; plain: string }
export interface Levers extends Base { currency: string; period_end: string; parts: Lever[]; movers: Mover[]; mover_book: string | null; change: string | null; percent: string | null }
export interface Series { series_key: string; name: string; kind: "fx" | "index_level"; level: string; level_date: string; month_change_pct: string | null; day_change_pct: string | null; trail_id: string; where: { text: string } }
export interface Markets extends Base { series: Series[] }
export interface LiqEntity { entity_id: string; name: string; cash: string; calls_30: string; cash_after_confirmed: string; cash_after_all: string; unconfirmed: number; problems: string[]; trail_id: string }
export interface Liquidity extends Base { currency: string; cash: string; calls_30: string; cash_after_confirmed: string; cash_after_all: string; partial: boolean; entities: LiqEntity[] }
export interface Daily { currency: string; as_of: string; period_end: string; period_start: string; nav: Nav; issued: Issued; returns: Returns; levers: Levers; markets: Markets; liquidity: Liquidity }

export const getDaily = (currency: string) => apiGet<Daily>(`/api/v1/consume/daily?currency=${encodeURIComponent(currency)}`);
