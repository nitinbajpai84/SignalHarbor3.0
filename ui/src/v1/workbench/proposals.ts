import { useCallback, useEffect, useState } from "react";

import { ApiError, apiSend } from "../../api/client";

// L2: the changes an agent proposed and nobody has decided. The chat views carry `proposals.pending`; accepting or turning one down
// goes to L2's routes, then the screen reloads its own view.
export interface Change { op: "add" | "change" | "remove"; path: string; before: string; after: string }
export interface Proposal { id: string; document: string; summary: string; changes: Change[]; by: string }
export interface Proposed { pending: Proposal[]; recent?: Proposal[] }

const base = (iid: string) => `/api/v1/intents/${encodeURIComponent(iid)}/proposals`;
const plain = (e: unknown) => (e instanceof ApiError && e.message ? e.message : "That did not go through. Please try again.");

export function useProposals(iid: string, from: Proposed | undefined, reload: () => unknown) {
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const act = useCallback(async (path: string, body: object) => {
    setBusy(true); setError("");
    try { await apiSend("POST", `${base(iid)}/${path}`, body); await reload(); } catch (e) { setError(plain(e)); } finally { setBusy(false); }
  }, [iid, reload]);
  useEffect(() => { setError(""); }, [from]);
  return {
    proposals: from?.pending ?? [], error, busy,
    onAccept: (id: string) => void act(`${encodeURIComponent(id)}/accept`, {}),
    onReject: (id: string, reason?: string) => void act(`${encodeURIComponent(id)}/reject`, { reason: reason ?? "" }),
  };
}
