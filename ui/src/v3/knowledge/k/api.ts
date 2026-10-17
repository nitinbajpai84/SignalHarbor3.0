import { apiGet } from "../../../api/client";

export type Kind = "person" | "entity" | "fund" | "source" | "file" | "document" | "recipe" | "figure" | "signal" | "rule" | "usecase" | "decision";
export interface Fact { text: string; source: string; at: string }
export interface KNode { id: string; kind: Kind; label: string; facts: Fact[]; stage?: string; waiting?: boolean; status?: string; versions?: number; fired?: number }
/** `up` is the end that the other end rests on; `why` is the plain-word reason for the link. */
export interface KEdge { from: string; to: string; label: string; up?: string; why?: string }
export interface Process { title: string; lanes: string[]; steps: { lane: string; text: string }[] }
export interface Thing { name: string; count: number; new: boolean }
export interface Knowledge { nodes: KNode[]; edges: KEdge[]; processes: Process[]; things: Thing[]; empty: boolean }

export const getKnowledge = () => apiGet<Knowledge>("/api/v3/knowledge");
