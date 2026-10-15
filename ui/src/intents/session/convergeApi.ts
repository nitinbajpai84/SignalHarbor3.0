import { useCallback, useEffect, useState } from "react";

import { ApiError, apiGet, apiSend } from "../../api/client";

// The calls and shapes of spec 37. One payload (GET /converge) feeds the count, the outcome card, What next and the late-thought panel.

export interface Row {
  ref: string; kind: "group" | "card"; text: string; group: string | null; anonymous: boolean; from?: string | null; backed: number;
  i_backed: boolean; replies: number; note_count?: number; samples?: string[]; cards?: Row[]; top?: boolean; tie?: number;
}
export interface Tie { among: string[]; free: number; count: number; resolved: boolean; picks: string[] }
export interface Source { text: string; source: string }
export interface Chosen {
  idea: string; why: string; why_sources: Source[]; kind: "group" | "card"; ref: string; what_it_takes: { text: string; source: string }[];
  proposed_by: { name: string }[]; proposed_unnamed: number; backed: number; backed_of: number; overridden_reason: string | null;
  drafted_by: string | null; fallback?: boolean; edited_by: string | null; confirmed_by: { name: string } | null; confirmed_at: string | null; by_rounds: Record<string, number>;
}
export interface Kept { ref: string; kind: string; text: string; from?: string; anonymous?: boolean; backed: { round1: number; round2: number | null }; runner_up: boolean }
export interface Late {
  opens_at: string; closes_at: string; open: boolean; frozen_at: string | null; can_add: boolean; names: "choice" | "named" | "anonymous"; limit: number;
  about: { ref: string; text: string }[]; thoughts: { text: string; about: string; at: string; anonymous: boolean; name: string | null }[];
}
export type Figure = number | number[] | { missing: string };
export interface PrefillQuestion { id: string; lead: string; answers: Record<string, string | string[]>; from_brainstorm: boolean }
export interface View {
  id: string; title: string; intent_state: string; tier: string; tz: string; ends: string | null;
  viewer: { organiser: boolean; seated: boolean; can_back: boolean };
  converge: { state: string; round?: number | null; max_rounds?: number; max_backs?: number; used?: number };
  have_backed: number; seated_count: number; rows: Row[]; mine: { ref: string; text: string }[]; tie: Tie | null; north: string;
  can: { open?: string | null; close?: string | null; round2?: string | null };
  next_kinds: string[]; candidates?: { ref: string; text: string; backed: number; top: boolean }[];
  outcome: { chosen: Chosen | null; ideas_kept: Kept[]; dropped: { ref: string; text: string }[]; next: unknown; rounds: number; confirmed?: boolean };
  numbers?: Record<string, Figure>; late: Late | null;
  prefill?: { questions: PrefillQuestion[] }; backlog_preview?: { title: string; why: string; raised_by: string; also_considered: string[]; review_date: string | null };
}

const base = (id: string) => `/api/intents/${id}`;
export const converge = {
  get: (id: string) => apiGet<View>(`${base(id)}/converge`),
  open: (id: string) => apiSend<View>("POST", `${base(id)}/converge/open`, {}),
  back: (id: string, candidate: string, on: boolean) => apiSend<View>("POST", `${base(id)}/converge/back`, { candidate, on }),
  close: (id: string, tie_picks?: string[]) => apiSend<View>("POST", `${base(id)}/converge/close`, tie_picks ? { tie_picks } : {}),
  round2: (id: string) => apiSend<View>("POST", `${base(id)}/converge/round2`, {}),
  draft: (id: string, ref?: string) => apiSend<View>("POST", `${base(id)}/outcome/draft`, ref ? { ref } : {}),
  edit: (id: string, body: Record<string, unknown>) => apiSend<View>("PUT", `${base(id)}/outcome`, body),
  confirm: (id: string) => apiSend<View>("POST", `${base(id)}/outcome/confirm`, {}),
  late: (id: string, body: { text: string; about: string; anonymous: boolean }) => apiSend<View>("POST", `${base(id)}/late-thoughts`, body),
};

export interface Loaded {
  view: View | null; failed: boolean; notice: string; busy: boolean;
  /** Runs one write, shows its plain-words refusal, and keeps the answer as the new view. */
  run: (call: () => Promise<View>) => Promise<boolean>;
  reload: () => void;
}

export function useConverge(intentId: string): Loaded {
  const [view, setView] = useState<View | null>(null);
  const [failed, setFailed] = useState(false);
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const reload = useCallback(() => {
    setFailed(false);
    converge.get(intentId).then(setView, () => setFailed(true));
  }, [intentId]);
  useEffect(reload, [reload]);
  const run = useCallback(async (call: () => Promise<View>) => {
    setBusy(true);
    setNotice("");
    try {
      setView(await call());
      return true;
    } catch (e) {
      setNotice(e instanceof ApiError ? e.message : "That did not save. Please try again.");
      return false;
    } finally {
      setBusy(false);
    }
  }, []);
  return { view, failed, notice, busy, run, reload };
}

/** A date in the company time zone (else UTC), for example "8 Oct, 15:00". */
export function when(iso: string | null | undefined, tz: string, withTime = true): string {
  if (!iso) return "";
  return new Date(iso).toLocaleString("en-GB", { timeZone: tz || "UTC", day: "numeric", month: "short", ...(withTime ? { hour: "2-digit", minute: "2-digit" } : {}) });
}

export function figure(f: Figure | undefined): string {
  if (f === undefined) return "Not available yet";
  if (typeof f === "object" && !Array.isArray(f)) return `Not available yet: ${f.missing}`;
  return Array.isArray(f) ? f.join(", ") : String(f);
}
