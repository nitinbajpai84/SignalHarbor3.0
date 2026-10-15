import { useCallback, useEffect, useState } from "react";

import { listPacks, type Pack, type Setup } from "../api";

/** A pack as /api/v3/setup and /api/v3/packs may carry it; intent_examples only when the server ships them. */
export interface PackRef { id: string; label: string; intent_examples?: string[] }
type RawPack = string | Partial<PackRef> | null | undefined;

/** /api/v3/setup answers `pack` as {id,label} or null (api.ts types it a string); accept both. */
export function packOf(s: Setup): PackRef | null {
  const p = s.pack as unknown as RawPack;
  if (!p) return null;
  if (typeof p === "string") return { id: p, label: p };
  return p.id ? { id: p.id, label: p.label ?? p.id, intent_examples: p.intent_examples } : null;
}

/** The company pack's example questions: from setup first, else from the packs list. [] when none are shipped. */
export async function packExamples(s: Setup): Promise<string[]> {
  const own = packOf(s)?.intent_examples ?? (s as Setup & { intent_examples?: string[] }).intent_examples;
  if (own?.length) return own;
  try {
    const { packs, current } = await listPacks();
    const p = packs.find((x) => x.id === current) as (Pack & { intent_examples?: string[] }) | undefined;
    return p?.intent_examples ?? [];
  } catch {
    return []; // the suggestions are optional; the page still works without them
  }
}

/** Loads once (fn must be stable): data, failed, and a retry. */
export function useLoad<T>(fn: () => Promise<T>) {
  const [data, setData] = useState<T | null>(null);
  const [failed, setFailed] = useState(false);
  const load = useCallback(() => {
    setFailed(false);
    fn().then(setData, () => setFailed(true));
  }, [fn]);
  useEffect(load, [load]);
  return { data, failed, load, setData };
}

/** The loading and error line every setup page shows before its data. */
export function Waiting({ failed, what, retry }: { failed: boolean; what: string; retry: () => void }) {
  return failed
    ? <p className="v3-err" role="alert">{what} did not load. <button type="button" onClick={retry}>Try again</button></p>
    : <p className="v3-mute" role="status">Loading {what.toLowerCase()}...</p>;
}
