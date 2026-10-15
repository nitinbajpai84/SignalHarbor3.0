import { csrfToken } from "../../api/client";

// V5W-7: a chat turn as server-sent events. The server (ChatStreamMiddleware) answers a POST that sends `Accept: text/event-stream` with
// `start`, then `delta` pieces of the reply, then `done` carrying the same JSON the plain route returns. Anything else falls back to
// that plain JSON, so a proxy that buffers or a server without the stream still works. fetch, not EventSource: it must send the CSRF header.

export interface ChatStreamHandlers {
  onStart?: () => void;
  /** Text so far (all pieces joined), for a growing reply bubble. */
  onText?: (soFar: string) => void;
  signal?: AbortSignal;
}

export class ChatStreamError extends Error {
  constructor(message: string, readonly status: number) { super(message); }
}

export function parseEvents(chunk: string): { event: string; data: unknown }[] {
  const out: { event: string; data: unknown }[] = [];
  for (const block of chunk.split("\n\n")) {
    const m = /^event: (\w+)\ndata: (.*)$/s.exec(block.trim());
    if (!m || !m[1] || m[2] === undefined) continue;
    try { out.push({ event: m[1], data: JSON.parse(m[2]) }); } catch { /* a cut piece: the next read completes it */ }
  }
  return out;
}

/** Send one chat message; resolves with the final JSON (the same object the plain route returns). */
export async function streamChat<T>(path: string, body: unknown, h: ChatStreamHandlers = {}): Promise<T> {
  const res = await fetch(path, {
    method: "POST", credentials: "same-origin", signal: h.signal,
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken(), Accept: "text/event-stream, application/json;q=0.5" },
    body: JSON.stringify(body),
  });
  if (!(res.headers.get("Content-Type") ?? "").startsWith("text/event-stream") || !res.body) {
    const json = (await res.json().catch(() => ({}))) as T & { message?: string };
    if (!res.ok) throw new ChatStreamError(json.message ?? "Something went wrong. Please try again.", res.status);
    h.onStart?.();
    return json; // the fallback: no stream, the whole answer at once
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "", text = "", final: T | undefined;
  for (;;) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value, { stream: !done });
    const cut = buffer.lastIndexOf("\n\n");
    const ready = cut < 0 ? "" : buffer.slice(0, cut + 2);
    buffer = cut < 0 ? buffer : buffer.slice(cut + 2);
    for (const { event, data } of parseEvents(ready)) {
      const d = data as { text?: string; message?: string; status?: number };
      if (event === "start") h.onStart?.();
      else if (event === "delta" && d.text) { text += d.text; h.onText?.(text); }
      else if (event === "done") final = data as T;
      else if (event === "error") throw new ChatStreamError(d.message ?? "Something went wrong. Please try again.", d.status ?? 500);
    }
    if (done) break;
  }
  if (final === undefined) throw new ChatStreamError("Something went wrong. Please try again.", 500);
  return final;
}
