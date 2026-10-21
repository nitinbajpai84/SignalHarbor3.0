// The service worker (public/sw.js) run against a fake cache and fetch: what is kept for offline, what is forgotten, and what a push shows.
import { readFileSync } from "node:fs";

const code = readFileSync(`${process.cwd()}/public/sw.js`, "utf-8"); // vitest runs from ui/
const ORIGIN = "http://h";
type Handler = (e: Record<string, unknown>) => void;

class Req extends Request { constructor(u: string | Request, i?: RequestInit) { super(typeof u === "string" ? new URL(u, ORIGIN) : u, i); } }

function boot(network: (r: Request) => Promise<Response>) {
  const handlers: Record<string, Handler> = {};
  const store = new Map<string, Map<string, Response>>();
  const key = (r: Request | string) => (typeof r === "string" ? new URL(r, ORIGIN).href : r.url);
  const cache = (n: string) => {
    if (!store.has(n)) store.set(n, new Map());
    const m = store.get(n)!;
    return { put: async (r: Request | string, res: Response) => { m.set(key(r), res); }, match: async (r: Request | string) => m.get(key(r))?.clone(),
             keys: async () => [...m.keys()].map((u) => new Req(u)), addAll: async () => undefined };
  };
  const caches = { open: async (n: string) => cache(n), delete: async (n: string) => store.delete(n), keys: async () => [...store.keys()],
                   match: async (r: Request | string) => { for (const m of store.values()) { const h = m.get(key(r)); if (h) return h.clone(); } return undefined; } };
  const shown: { title: string; opts: { body: string; data: { url: string } } }[] = [];
  const self = { location: { origin: ORIGIN }, addEventListener: (t: string, fn: Handler) => { handlers[t] = fn; }, skipWaiting: () => undefined,
                 clients: { claim: () => undefined, matchAll: async () => [], openWindow: vi.fn() },
                 registration: { showNotification: async (title: string, opts: never) => { shown.push({ title, opts }); } } };
  new Function("self", "caches", "fetch", "Request", code)(self, caches, network, Req);
  const fetchAs = async (r: Request) => {
    let p: Promise<Response> | undefined;
    handlers.fetch!({ request: r, respondWith: (x: Promise<Response>) => { p = x; } });
    return p;
  };
  const push = async () => { let p: Promise<unknown> = Promise.resolve(); handlers.push!({ waitUntil: (x: Promise<unknown>) => { p = x; } }); await p; };
  return { fetchAs, store, shown, push };
}
const json = (b: unknown) => new Response(JSON.stringify(b), { headers: { "Content-Type": "application/json" } });

test("the last Desk is read from the keep when the network is gone, and a fresh one always wins", async () => {
  let online = true;
  let n = 0;
  const w = boot(async () => { if (!online) throw new TypeError("offline"); return json({ n: ++n }); });
  expect(await (await w.fetchAs(new Req("/api/v3/desk"))!)!.json()).toEqual({ n: 1 });
  expect(await (await w.fetchAs(new Req("/api/v3/desk"))!)!.json()).toEqual({ n: 2 });
  online = false;
  expect(await (await w.fetchAs(new Req("/api/v3/desk"))!)!.json()).toEqual({ n: 2 });
});

test("other API reads are never kept, and nothing from another site is touched", async () => {
  const w = boot(async () => json({}));
  expect(await w.fetchAs(new Req("/api/v3/files"))).toBeUndefined();
  expect(await w.fetchAs(new Req("https://elsewhere.example.test/api/v3/desk"))).toBeUndefined();
  expect(await w.fetchAs(new Req("/api/v3/threads", { method: "POST", body: "{}" }))).toBeUndefined();
});

test("signing in or out empties the kept answers, so the next person never sees the last person's", async () => {
  const w = boot(async () => json({ secret: 1 }));
  await w.fetchAs(new Req("/api/v3/portal"));
  expect(w.store.get("sh-data-v1")?.size).toBe(1);
  await w.fetchAs(new Req("/api/auth/logout", { method: "POST", body: "{}" }));
  await new Promise((r) => setTimeout(r, 0));
  expect(w.store.has("sh-data-v1")).toBe(false);
});

test("offline, an Ask shows the last answer and says it is not the new one", async () => {
  let online = true;
  const w = boot(async () => { if (!online) throw new TypeError("offline"); return json({ answer: "Cash is 4.14m.", trace: [], used: [] }); });
  const ask = () => new Req("/api/v3/ask", { method: "POST", body: JSON.stringify({ text: "cash?" }) });
  await w.fetchAs(ask());
  online = false;
  const got = await (await w.fetchAs(ask())!)!.json();
  expect(got.answer).toMatch(/^You are offline\. This is the last answer you saw, not an answer to this question: Cash is 4\.14m\./);
  const cold = boot(async () => { throw new TypeError("offline"); });
  await expect(cold.fetchAs(ask())!).rejects.toThrow();
});

test("a push shows the words waiting in the inbox, or plain words when they cannot be fetched", async () => {
  const w = boot(async () => json([{ title: "Approval for you", body: "Approve the school fee distribution", url: "/v3/portal#approvals" }]));
  await w.push();
  expect(w.shown).toEqual([expect.objectContaining({ title: "Approval for you", opts: expect.objectContaining({ body: "Approve the school fee distribution", data: { url: "/v3/portal#approvals" } }) })]);
  const lost = boot(async () => { throw new TypeError("offline"); });
  await lost.push();
  expect(lost.shown[0]?.title).toBe("Signal Harbor");
});
