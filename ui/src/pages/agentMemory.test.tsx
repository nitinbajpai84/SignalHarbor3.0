import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import { setSessionExpiredHandler } from "../api/client";
import { SessionProvider } from "../useSession";
import AgentMemory from "./AgentMemory";
import MemoryPage from "./MemoryPage";

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const calls: { method: string; url: string; body?: unknown }[] = [];
let items = [
  { id: "m-1", agent: "lumen", agent_name: "Lumen", kind: "preference", text: "Prefers: blue for chart lines", sure: "inferred", at: "2026-10-09T08:00:00", source: { said: "line in blue" } },
  { id: "m-2", agent: "north", agent_name: "North", kind: "fact", text: "Reports to the family council", sure: "said", at: "2026-10-08T08:00:00", source: {} },
];

function mock(roles: string[] = ["participant"]) {
  calls.length = 0;
  document.cookie = "sh_csrf=tok";
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    const method = init?.method ?? "GET";
    calls.push({ method, url, body: init?.body ? JSON.parse(String(init.body)) : undefined });
    if (url === "/api/auth/me") return json(200, { display_name: "Ann", company_id: "co-a", roles });
    if (url.startsWith("/api/v1/memory/me/") && method === "DELETE") { items = items.filter((i) => !url.endsWith(i.id)); return json(200, { forgotten: "x" }); }
    if (url.startsWith("/api/v1/memory/me/") && method === "PATCH") { items = items.map((i) => (url.endsWith(i.id) ? { ...i, text: String((JSON.parse(String(init?.body)) as { text: string }).text) } : i)); return json(200, items[0]); }
    if (url === "/api/v1/memory/me") return json(200, { items });
    if (url === "/api/v1/memory/company") return json(200, { items: [{ id: "c-1", agent: "company", agent_name: "the company", kind: "fact", text: "Report in USD unless asked", sure: "said", at: "2026-10-01T00:00:00", source: {} }], may_edit: roles.includes("company_admin") });
    return json(200, { entries: [] });
  }));
}
afterEach(() => { vi.unstubAllGlobals(); setSessionExpiredHandler(null); });

it("lists what each agent remembers, with when and how sure", async () => {
  mock();
  render(<AgentMemory />);
  expect(await screen.findByText("Prefers: blue for chart lines")).toBeInTheDocument();
  expect(screen.getByText("Lumen remembers")).toBeInTheDocument();
  expect(screen.getByText("North remembers")).toBeInTheDocument();
  expect(screen.getByText(/Preference, 2026-10-09, worked out from what you asked/)).toBeInTheDocument();
  expect(screen.getByText(/From: "line in blue"/)).toBeInTheDocument();
});

it("correcting a line sends the new words, forgetting one deletes just that line", async () => {
  mock();
  render(<AgentMemory />);
  await userEvent.click((await screen.findAllByRole("button", { name: "Correct" }))[0]!);
  const box = screen.getByLabelText("Correct this memory");
  await userEvent.clear(box); await userEvent.type(box, "I like red lines");
  await userEvent.click(screen.getByRole("button", { name: "Save correction" }));
  await waitFor(() => expect(calls).toContainEqual({ method: "PATCH", url: "/api/v1/memory/me/m-1", body: { text: "I like red lines" } }));
  await userEvent.click((await screen.findAllByRole("button", { name: "Forget this" }))[1]!);
  await waitFor(() => expect(calls).toContainEqual({ method: "DELETE", url: "/api/v1/memory/me/m-2", body: undefined }));
  expect(await screen.findByText("I like red lines")).toBeInTheDocument();
});

it("says plainly when nothing has been learned yet", async () => {
  mock(); items = [];
  render(<AgentMemory />);
  expect(await screen.findByText(/have not learned anything from your conversations yet/)).toBeInTheDocument();
});

it("a failed load names what happened and offers another try", async () => {
  mock();
  vi.stubGlobal("fetch", vi.fn(async () => json(500, { error: "failed", message: "x" })));
  render(<AgentMemory />);
  expect(await screen.findByRole("alert")).toHaveTextContent(/did not load/);
  expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
});

it("company lines are read by everyone and changed only by those who may", async () => {
  mock(["participant"]);
  const { unmount } = render(<AgentMemory company canEdit={false} />);
  expect(await screen.findByText("Report in USD unless asked")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Forget this" })).toBeNull();
  expect(screen.queryByLabelText("Add a company note")).toBeNull();
  unmount();
  render(<AgentMemory company canEdit />);
  expect(await screen.findByRole("button", { name: "Forget this" })).toBeInTheDocument();
  expect(screen.getByLabelText("Add a company note")).toBeInTheDocument();
});

it("the settings page shows the new section above the older lists", async () => {
  mock(); items = [{ id: "m-1", agent: "lumen", agent_name: "Lumen", kind: "preference", text: "Prefers: SGD", sure: "said", at: "2026-10-09T08:00:00", source: {} }];
  render(<MemoryRouter><SessionProvider><MemoryPage /></SessionProvider></MemoryRouter>);
  expect(await screen.findByText("Prefers: SGD")).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Learned from your conversations" })).toBeInTheDocument();
});
