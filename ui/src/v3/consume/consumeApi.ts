// Consume client: GET /api/v3/consume and the cached POST /api/v3/ask (docs/v3/HARBOR-SPEC.md, 15 Oct).
import { apiGet, apiSend } from "../../api/client";
import type { AskAnswer } from "../api";

export interface Reading { label: string; value: string; change: string; stale: boolean; code?: string; dated?: string | null }
export interface ConsumeAnswer extends AskAnswer {
  cached?: boolean; ms?: number; as_of?: string | null; series?: number[]; rows?: { label: string; value: string }[]; source?: string;
}
export interface ConsumeData {
  office?: string; as_of: string | null; figures: Reading[]; watchlist: Reading[]; boards: { id: string; title: string }[];
  note: { headline: string } | null; reports: { name: string; href: string }[]; golden: { q: string }[]; answer?: (ConsumeAnswer & { q: string }) | null;
}

export const getConsume = () => apiGet<ConsumeData>("/api/v3/consume");
export const askConsume = (text: string) => apiSend<ConsumeAnswer>("POST", "/api/v3/ask", { text });
