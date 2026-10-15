// Test helper: answers fetch by "METHOD path" or path; anything unlisted fails with 500.
export const json = (b: unknown, status = 200) => new Response(JSON.stringify(b), { status, headers: { "Content-Type": "application/json" } });
export function routes(map: Record<string, () => Response>) {
  return vi.fn(async (url: string | URL | Request, init?: RequestInit) => {
    const u = String(url);
    return (map[`${init?.method ?? "GET"} ${u}`] ?? (init?.method && init.method !== "GET" ? undefined : map[u]) ?? (() => json({}, 500)))();
  });
}
export const voiceOff = { "/api/v1/voice": () => json({ available: false, note: null }) };
