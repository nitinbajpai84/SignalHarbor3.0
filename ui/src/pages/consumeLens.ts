import type { Feed } from "./FeedsPage";

// The four business views (C37). On screen they are "business views"; in code and on the wire `lens` stays.
// Wire shapes follow spec 60 (GET /api/company/consume/lenses and /{lens}); every field is optional on read.

export interface LensCounts { measures?: number; outside?: number; briefs?: number; building?: number; proving?: number; consider?: number }
export interface LensRow { key: string; slug?: string; name: string; question?: string; measures?: string[]; counts?: LensCounts; empty?: string | null }
export interface BuildingRow { id: string; title: string; href?: string | null; stage?: string; organiser?: string | null; measure?: string | null; verdict?: string | null }
export interface ConsiderRow { id: string; title: string; state?: string; line?: string | null; href?: string }
export interface LensBrief { id: string; title: string; summary: string; source: string; measure_moves?: { code: string; name: string }[] }
export interface MeasureRow { code: string; name: string; mark?: string | null; confirmed_by?: string | null }
export interface LensDetail extends LensRow {
  briefs?: LensBrief[]; feeds?: Feed[]; building?: BuildingRow[]; consider?: ConsiderRow[]; measure_rows?: MeasureRow[]; outside_line?: string | null;
}
export interface LensList { lenses: LensRow[]; has_line_of_work?: boolean; not_in_a_lens?: number }

export const LENS_NAMES: Record<string, string> = { new_revenue: "New revenue", process_cost: "Process cost", retention: "Retention", risk: "Risk" };
export const LENS_ASKS: Record<string, string> = {
  new_revenue: "What could earn more from what the office already holds?",
  process_cost: "Where do staff hours and fees go?",
  retention: "Do the family and the next generation use and trust our reports?",
  risk: "What could hurt the family's capital?",
};
/** Page keys use hyphens (`process-cost`); the wire keeps underscores. */
export const slug = (k: string) => k.replace(/_/g, "-");
export const wire = (k: string) => k.replace(/-/g, "_");

export const VIEW_NOTE = "Business views group what is already here. They add no figure of their own.";
