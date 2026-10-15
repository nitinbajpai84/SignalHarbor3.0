import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import LibraryPage from "./LibraryPage";
import { routes } from "./routes";

// UX3: the Library page lists every document the person may see; fetch stubbed, synthetic data.
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const item = (id: string, name: string, more: object = {}) => ({
  id, name, kind: "document", note: "", uploaded_by: "Seeded", at: "2026-10-08T09:00:00Z", size: 10, visibility: "company",
  path: `documents/${name}`, tags: [], mine: false, can_change: false, ...more,
});
const FOLDERS = [
  { folder: "Policies and rules", icon: "policy", count: 1, items: [item("a", "policy.md", { mine: true, can_change: true })] },
  { folder: "Statements", icon: "statement", count: 2, items: [item("b", "demo statements.csv"), item("c", "board minutes.pdf", { locked: true, sensitivity: "restricted", access: "request", preview: { contains_personal_data: false, kinds: [] } })] },
];

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    if (url === "/api/intents") return json(200, [{ id: "i7" }, { id: "i9" }]);  // INT3: the viewer's projects
    if (url === "/api/v1/intents/i9/context") return json(200, { library_ids: ["b"] });
    if (url === "/api/v1/intents/i7/context") return json(200, { library_ids: [] });
    if (!url.startsWith("/api/v1/library/folders")) return json(404, {});
    const q = decodeURIComponent(url.split("?q=")[1] ?? "").toLowerCase();
    const folders = FOLDERS.map((f) => ({ ...f, items: f.items.filter((i) => i.name.toLowerCase().includes(q)) })).map((f) => ({ ...f, count: f.items.length })).filter((f) => f.count);
    return json(200, { folders, sorting: false, all: ["Policies and rules", "Statements", "Other"] });
  }));
});

const page = (url = "/centre/library?iid=i1") => render(<MemoryRouter initialEntries={[url]}><LibraryPage /></MemoryRouter>);

test("the route is registered", () => expect(routes.map((r) => r.path)).toContain("library"));

test("lists every file with folders, counts, Open, locked rows and owner controls, without ticks", async () => {
  page();
  expect(await screen.findByRole("button", { name: "Statements, 2 files" })).toBeInTheDocument();
  expect(screen.getByText("demo statements.csv")).toBeInTheDocument();
  expect(screen.queryByRole("checkbox", { name: /Use .* in this conversation/ })).toBeNull();
  expect(screen.getByRole("link", { name: "Open policy.md in a new tab" })).toHaveAttribute("href", "/centre/build/i1/source?file=documents%2Fpolicy.md");
  expect(screen.getByRole("button", { name: /Request access/ })).toBeInTheDocument();
  expect(screen.getByRole("switch", { name: "Share policy.md with the company" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Delete" })).toBeInTheDocument();
});

test("search runs across folders", async () => {
  page();
  fireEvent.click(await screen.findByRole("button", { name: "Policies and rules, 1 file" }));
  fireEvent.change(screen.getByRole("searchbox", { name: "Search the library" }), { target: { value: "statements" } });
  expect(await screen.findByText("demo statements.csv")).toBeInTheDocument();
  await waitFor(() => expect(screen.queryByText("policy.md")).toBeNull());
});

test("from the menu (no ?iid=) Open uses the project the file is ticked in, else the first project", async () => {
  page("/centre/library");
  expect(await screen.findByRole("link", { name: "Open demo statements.csv in a new tab" })).toHaveAttribute("href", "/centre/build/i9/source?file=documents%2Fdemo%20statements.csv");
  expect(screen.getByRole("link", { name: "Open policy.md in a new tab" })).toHaveAttribute("href", "/centre/build/i7/source?file=documents%2Fpolicy.md");
});

test("a person the library is not open to is told so and who to ask, not to try again (C2-UC7-05)", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => json(403, { error: "not_allowed", message: "Not open to you." })));
  page();
  expect(await screen.findByText(/library is open to the sponsor, the analysts and the company administrator/)).toBeInTheDocument();
  expect(screen.queryByText(/try again/)).toBeNull();
});
