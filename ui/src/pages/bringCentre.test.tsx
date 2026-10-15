import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import { setSessionExpiredHandler } from "../api/client";
import BringCentre, { lastWritten } from "./BringCentre";

// "Bring what you have", new look: the five screen states, the nine cards with their pills, the side panels, the request text. fetch is stubbed.

const TITLES = ["People and roles", "Strategy and intent", "Reporting today", "Definitions", "Processes", "Data landscape", "Governance", "Sample data", "Constraints"];
const groups = (over: Record<number, object> = {}) =>
  TITLES.map((title, i) => ({ id: i + 1, key: `g${i + 1}`, title, required: i % 2 === 0, state: "missing", reason: "Nothing has been sent yet.", files: [] as string[], ...over[i + 1] }));
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const cell = (value: unknown, from: string, at: string) => ({ value, mark: "stated", by: "Lens", at, from });
const PROFILE = {
  people: { a: { name: cell("Mei Tan", "people.csv", "2026-01-01T10:00") } },
  systems: { s: { name: cell("Ledger", "landscape.xlsx", "2026-01-02T10:00") } },
  reported_figures: { f: { measure: cell("AUM", "pack.pdf", "2026-01-03T10:00"), owner: cell("Mei Tan", "pack.pdf", "2026-01-04T10:00") } },
  constraints: { c: { what: cell("No cloud", "rules.docx", "2026-01-05T10:00") } },
};
const calls: { method: string; url: string }[] = [];

function mock(w: { ready?: object; hold?: boolean; status?: number; profileFails?: boolean } = {}) {
  calls.length = 0;
  document.cookie = "sh_csrf=tok";
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    calls.push({ method: init?.method ?? "GET", url });
    if (url === "/api/profile/readiness") {
      if (w.hold) return new Promise<Response>(() => undefined);
      if (w.status) return json(w.status, { error: w.status === 403 ? "forbidden" : "x", message: "x" });
      return json(200, w.ready ?? { groups: groups(), percent: 0, read: 0, sentence: "x", asks: [] });
    }
    if (url === "/api/profile") return w.profileFails ? json(500, { error: "x", message: "x" }) : json(200, PROFILE);
    if (/\/ask$/.test(url)) return json(200, { group: 3, holder: null, email: { subject: "One thing", body: "Hello,\n\nUpload it here: /company/bring?ask=pf-abc", link: "/company/bring?ask=pf-abc" } });
    return json(404, {});
  }));
}
const open = () => render(<MemoryRouter><BringCentre /></MemoryRouter>);

afterEach(() => { vi.unstubAllGlobals(); setSessionExpiredHandler(null); });

describe("Bring what you have, new look: five states", () => {
  test("loading", async () => {
    mock({ hold: true });
    open();
    expect(await screen.findByRole("heading", { name: "Bring what you have" })).toBeInTheDocument();
    expect(await screen.findByRole("status")).toHaveTextContent("Loading");
  });

  test("empty: nothing brought yet, still the nine cards", async () => {
    mock();
    open();
    expect(await screen.findByText(/Nothing has been brought yet/)).toBeInTheDocument();
    expect(screen.getAllByRole("article")).toHaveLength(9);
    expect(screen.getAllByText("NOT BROUGHT YET")).toHaveLength(9);
  });

  test("error: one sentence and a way to try again", async () => {
    mock({ status: 500 });
    open();
    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });

  test("refused", async () => {
    mock({ status: 403 });
    open();
    expect(await screen.findByText("You do not have access to this. Ask your administrator.")).toBeInTheDocument();
    expect(screen.queryAllByRole("article")).toHaveLength(0);
  });

  test("populated: header line, bar, nine cards with pills and mono file names, the right panel", async () => {
    mock({ ready: { groups: groups({ 1: { state: "read", files: ["people.csv"] }, 3: { state: "partly", files: ["pack.pdf", "b.xlsx"] }, 7: { sealed: 1 } }), percent: 35, read: 1, sentence: "x",
      asks: [{ group: 3, title: "Reporting today", holder: null }] } });
    open();
    expect(await screen.findByText("3 files · 1 of 9 read · everything stays in this company's space")).toBeInTheDocument();
    expect(screen.getByRole("progressbar", { name: "How much Lens, who writes the definitions, can draft" })).toHaveAttribute("aria-valuenow", "35");
    expect(screen.getAllByRole("article")).toHaveLength(9);
    const reporting = screen.getByRole("article", { name: "Reporting today" });
    expect(within(reporting).getByText("PARTLY")).toBeInTheDocument();
    expect(within(reporting).getByText("pack.pdf")).toBeInTheDocument();
    expect(within(screen.getByRole("article", { name: "People and roles" })).getByText("READ")).toBeInTheDocument();
    expect(within(screen.getByRole("article", { name: "Governance" })).getByText("1 SEALED")).toBeInTheDocument();
    expect(within(reporting).getByText("Drop another file")).toBeInTheDocument();
    const lives = screen.getByRole("region", { name: "Where this lives" });
    expect(within(lives).getAllByRole("listitem")).toHaveLength(5);
    expect(within(lives).getByText("Sealed files are never read and never leave.")).toBeInTheDocument();
    // the four newest cells, with their source
    const wrote = within(screen.getByRole("region", { name: "What Lens wrote, with its source" })).getAllByRole("listitem");
    expect(wrote.map((l) => l.textContent)).toEqual(["No cloud from rules.docx", "Mei Tan from pack.pdf", "AUM from pack.pdf", "Ledger from landscape.xlsx"]);
  });

  test("a missing profile reads Not available yet; the page still works", async () => {
    mock({ profileFails: true, ready: { groups: groups({ 1: { state: "read", files: ["a.csv"] } }), percent: 5, read: 1, sentence: "x", asks: [] } });
    open();
    expect(await within(await screen.findByRole("region", { name: "What Lens wrote, with its source" })).findByText("Not available yet")).toBeInTheDocument();
  });

  test("Write the request shows text to copy and sends nothing", async () => {
    mock({ ready: { groups: groups({ 3: { state: "partly", files: ["x.csv"] } }), percent: 10, read: 0, sentence: "x", asks: [{ group: 3, title: "Reporting today", holder: null }] } });
    open();
    await userEvent.setup().click(await screen.findByRole("button", { name: "Write the request for Reporting today" }));
    expect(((await screen.findByRole("textbox", { name: "Request for Reporting today" })) as HTMLTextAreaElement).value).toContain("Subject: One thing");
    expect(calls.filter((c) => c.method === "POST").map((c) => c.url)).toEqual(["/api/profile/inputs/3/ask"]);
  });
});

test("lastWritten keeps the newest four cells that name their source", () => {
  expect(lastWritten(PROFILE).map((w) => w.from)).toEqual(["rules.docx", "pack.pdf", "pack.pdf", "landscape.xlsx"]);
  expect(lastWritten({})).toEqual([]);
});
