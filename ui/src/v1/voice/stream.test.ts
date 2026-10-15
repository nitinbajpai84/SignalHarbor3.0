import { ChatStreamError, parseEvents, streamChat } from "./stream";

const sse = (...evs: [string, unknown][]) => evs.map(([e, d]) => `event: ${e}\ndata: ${JSON.stringify(d)}\n\n`).join("");
const reply = (body: string, type = "text/event-stream", status = 200) => new Response(body, { status, headers: { "Content-Type": type } });
afterEach(() => vi.unstubAllGlobals());

test("pieces grow the reply and done returns the final JSON; the request asks for a stream with the CSRF header", async () => {
  const fetchMock = vi.fn(async () => reply(sse(["start", {}], ["delta", { text: "Open breaks " }], ["delta", { text: "are seven." }], ["done", { reply: "Open breaks are seven." }])));
  vi.stubGlobal("fetch", fetchMock);
  const seen: string[] = [];
  let started = 0;
  const out = await streamChat<{ reply: string }>("/api/v1/consume/chat", { text: "x" }, { onStart: () => started++, onText: (t) => seen.push(t) });
  expect(out.reply).toBe("Open breaks are seven.");
  expect(seen).toEqual(["Open breaks ", "Open breaks are seven."]);
  expect(started).toBe(1);
  const init = (fetchMock.mock.calls[0] as unknown as [string, RequestInit])[1];
  expect(String((init.headers as Record<string, string>).Accept)).toContain("text/event-stream");
  expect(Object.keys(init.headers as object)).toContain("X-CSRF-Token");
});

test("a server without the stream still works: the plain JSON is the answer", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => reply(JSON.stringify({ reply: "Hello." }), "application/json")));
  expect(await streamChat<{ reply: string }>("/api/v1/consume/chat", {})).toEqual({ reply: "Hello." });
});

test("a refusal says what happened in the server's words", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => reply(sse(["start", {}], ["error", { status: 403, message: "You do not have access to this." }]))));
  await expect(streamChat("/api/v1/consume/chat", {})).rejects.toMatchObject({ message: "You do not have access to this.", status: 403 });
  vi.stubGlobal("fetch", vi.fn(async () => reply(JSON.stringify({ message: "Too long." }), "application/json", 400)));
  await expect(streamChat("/api/v1/consume/chat", {})).rejects.toBeInstanceOf(ChatStreamError);
});

test("a piece cut in the middle is kept until the rest arrives", () => {
  expect(parseEvents('event: delta\ndata: {"text":"a"}\n\nevent: delta\ndata: {"te')).toHaveLength(1);
});
