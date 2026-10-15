// W2: the pain-point demo. Shape is what sh_platform/v1/k12_painpoints.py sends.
import { apiGet } from "../../api/client";

export type Coverage = "strong" | "partial" | "not_in_scope";
export interface PainPoint { id: string; cluster: string; title: string; severity: "high" | "medium" | "low"; does: string; coverage: Coverage; reason: string; use_case: string; link: string }
export interface PainPoints { source: "sample" | "local"; total: number; counts: Record<Coverage, number>; clusters: { cluster: string; items: PainPoint[] }[] }

export const getPainPoints = (name = "") => apiGet<PainPoints>(`/api/v1/demo/painpoints${name ? `?name=${encodeURIComponent(name)}` : ""}`);
