import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { ThemeProvider } from "../../theme";
import ContextBox from "./ContextBox";

// C4's Context box against c4_routes (fetch stubbed, synthetic data): tick a suggestion, the duplicate question, the share switch.
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const item = (id: string, name: string, extra: object = {}) => ({
  id, name, kind: "document", note: "", uploaded_by: "Seeded", at: "2026-10-08T09:00:00Z", size: 10, visibility: "company",
  path: `documents/${name}`, tags: [], mine: false, can_change: false, ...extra,
});
const POLICY = item("lib_a", "access-policy.md");
const MINE = item("lib_m", "performance.csv", { kind: "sample", note: "performance reporting file", uploaded_by: "Meredith Shaw", visibility: "private", mine: true, can_change: true });

function mock() {
  const calls: { method: string; url: string; body?: Record<string, unknown> }[] = [];
  let ticked: string[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    const method = init?.method ?? "GET";
    const body = init?.body ? JSON.parse(String(init.body)) : undefined;
    calls.push({ method, url, body });
    const all = [POLICY, MINE];
    if (url.endsWith("/context/suggestions")) return json(200, ticked.includes("lib_a") ? [] : [POLICY]);
    if (url.endsWith("/context") && method === "PUT") ticked = body.library_ids;
    if (url.endsWith("/context")) return json(200, { library_ids: ticked, items: all.filter((i) => ticked.includes(i.id)) });
    if (url === "/api/v1/library/proposal") return json(200, { sensitivity: "open", topics: ["Policies and rules"], pii: { found: false, kinds: [], where: [] }, by: "rules", message: "Looks like policies and rules. No personal data found. Keep as Open?", topic_list: ["Policies and rules"] });
    if (url === "/api/v1/library" && method === "POST") return json(200, { duplicate: { id: "lib_a", name: "access-policy.md", uploaded_by: "Grace Ward", at: "2026-10-01T09:00:00Z" } });
    if (url.startsWith("/api/v1/library/") && method === "PUT") return json(200, { ...MINE, visibility: body.visibility });
    if (url.startsWith("/api/v1/library")) return json(200, all);
    return json(404, {});
  }));
  return calls;
}
const view = () => render(<ThemeProvider><ContextBox iid="i1" agent="North" skill="Family office skill: what others usually track" /></ThemeProvider>);

afterEach(() => vi.unstubAllGlobals());

test("a suggestion is never pre-ticked; ticking it puts it in this conversation", async () => {
  const calls = mock();
  view();
  expect(await screen.findByText(/These may be relevant/)).toBeInTheDocument();
  expect(screen.getByText(/Nothing ticked yet/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("checkbox", { name: /access-policy.md/ }));
  expect(await screen.findByRole("button", { name: "Untick access-policy.md" })).toBeInTheDocument();
  expect(calls.find((c) => c.method === "PUT")?.body).toEqual({ library_ids: ["lib_a"] });
  expect(screen.getByText("Family office skill: what others usually track")).toBeInTheDocument();
});

test("a duplicate upload asks, and Use it ticks the one already there", async () => {
  const calls = mock();
  view();
  await screen.findByText(/Nothing ticked yet/);
  fireEvent.change(screen.getByLabelText("Say what this is"), { target: { value: "access policy" } });
  fireEvent.change(screen.getByLabelText("Add files for North"), { target: { files: [new File(["x"], "access.md")] } });
  fireEvent.click(await screen.findByRole("button", { name: "Add to the library" }));  // K1: the upload step
  expect(await screen.findByText(/already in the library, uploaded by Grace Ward/)).toBeInTheDocument();
  expect(calls.find((c) => c.method === "POST" && c.url === "/api/v1/library")?.body).toMatchObject({ name: "access.md", note: "access policy", iid: "i1" });
  fireEvent.click(screen.getByRole("button", { name: "Use it" }));
  expect(await screen.findByRole("button", { name: "Untick access-policy.md" })).toBeInTheDocument();
});

test("my own file has a share switch", async () => {
  const calls = mock();
  view();
  await screen.findByText(/Nothing ticked yet/);
  const details = screen.getByText("All my files and shared files").closest("details")!;
  details.open = true;
  fireEvent(details, new Event("toggle"));
  const sw = await screen.findByRole("switch", { name: "Share performance.csv with the company" });
  expect(screen.queryByRole("switch", { name: /access-policy/ })).toBeNull();  // not mine: no switch
  fireEvent.click(sw);
  await waitFor(() => expect(calls.find((c) => c.method === "PUT" && c.url === "/api/v1/library/lib_m")?.body).toEqual({ visibility: "company" }));
});
