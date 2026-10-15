import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import LibraryPage from "./LibraryPage";
import LibraryViewPage from "./LibraryViewPage";
import { routes } from "./routes";

// W06: the project-free viewer page and the Open link that points at it; fetch stubbed, synthetic data.
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

test("the route is registered", () => expect(routes.map((r) => r.path)).toContain("library/view"));

test("shows the file as numbered lines", async () => {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    expect(url).toBe("/api/v1/library/view?file=documents%2Fpolicy.md");
    return json(200, { name: "policy.md", lines: [{ n: 1, text: "Access policy" }, { n: 2, text: "Read only" }] });
  }));
  render(<MemoryRouter initialEntries={["/centre/library/view?file=documents%2Fpolicy.md"]}><LibraryViewPage /></MemoryRouter>);
  expect(await screen.findByText("Read only")).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "policy.md" })).toBeInTheDocument();
});

test("a refusal shows a sentence, not a crash", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => json(404, { detail: "We could not find that file in the library." })));
  render(<MemoryRouter initialEntries={["/centre/library/view?file=x"]}><LibraryViewPage /></MemoryRouter>);
  expect(await screen.findByRole("alert")).toBeInTheDocument();
});

test("Open points at the viewer when the person has no project", async () => {
  const row = { id: "a", name: "policy.md", kind: "document", note: "", uploaded_by: "Seeded", at: "2026-10-08T09:00:00Z", size: 1, visibility: "company",
    path: "documents/policy.md", tags: [], mine: false, can_change: false };
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    if (url === "/api/intents") return json(200, []);
    if (url.startsWith("/api/v1/library/folders")) return json(200, { sorting: false, all: ["Other"], folders: [{ folder: "Other", icon: "x", count: 1, items: [row] }] });
    return json(404, {});
  }));
  render(<MemoryRouter initialEntries={["/centre/library"]}><LibraryPage /></MemoryRouter>);
  fireEvent.click(await screen.findByRole("button", { name: "Other, 1 file" }));
  expect(await screen.findByRole("link", { name: "Open policy.md in a new tab" })).toHaveAttribute("href", "/centre/library/view?file=documents%2Fpolicy.md");
});
