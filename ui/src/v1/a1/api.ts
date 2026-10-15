// A1: Span's conversation (sh_platform/v1/a1_routes.py), through the shared client.
import { apiGet, apiSend } from "../../api/client";
import type { ScanKpi } from "../b2/api";
import type { Used } from "../teach/api";

export interface Turn { id: string; by: "person" | "span"; name: string; text: string; at: string; did: string[] }
export interface ModelTable { table: string; kind: "fact" | "dimension"; grain: string; keys: string[]; relationships: string[]; history: string; measures: string[] }
export interface Question { id: string; question: string; default: string; why: string; answer: string; settled: boolean; defaulted?: boolean }
export interface LayerItem { id: string; label: string; about: string }
export interface Layers { columns: { kind: string; title: string; items: LayerItem[] }[]; links: { from: string; to: string }[] }
export interface Blueprint {
  used?: Used[]; intent_id: string; title: string; skill: string;
  sow: {
    state: string; version: number; signature: { name: string; role: string; at: string } | null;
    kpis: { code: string; name: string; status: string }[]; sources: { id: string; name: string; kind: string }[];
    catalogue: { table: string; layer: string; meaning: string }[];
  };
  turns: Turn[]; state: "open" | "ready" | "approved"; approved_by: string | null; approved_at: string | null; greeting: string;
  data_model: ModelTable[]; questions: Question[]; scope: string[];
  design: { lines: string[]; fallback: boolean; message: string | null; counts: Record<string, number>; at: string } | null;
  layers: Layers | null;
  scan: { kpis: (ScanKpi & { name: string })[]; agreed: { by: string; at: string; scope: string[] } | null } | null;
  mapping: { version: number; rows: number; unclear: number; fallback: boolean } | null;
  summary: string[]; can_talk: boolean; can_approve: boolean; proposals?: Proposed;
}

const base = (iid: string) => `/api/v1/build/${encodeURIComponent(iid)}/blueprint`;
export const getBlueprint = (iid: string) => apiGet<Blueprint>(`${base(iid)}/chat`);
export { kindOf, readBase64 } from "../i3/api";
import type { Proposed } from "../workbench/proposals";
export interface UpFile { name: string; data: string; kind: "sample" | "document" }
/** V1: files go inline as base64 and are stored where I2 stores them (a sample under landing/, a document under documents/). */
export const sendSpan = (iid: string, text: string, files: UpFile[] = []) =>
  apiSend<Blueprint>("POST", `${base(iid)}/chat`, files.length ? { text, files } : { text });
export const approve = (iid: string) => apiSend<Blueprint>("POST", `${base(iid)}/approve`);
