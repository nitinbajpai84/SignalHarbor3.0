import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { ThemeProvider } from "../../theme";
import { SessionProvider } from "../../useSession";
import TrailPanel from "./TrailPanel";

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
afterEach(() => vi.unstubAllGlobals());
const keys = ["source", "file", "read", "checked", "stored", "used_by"];
const labels = ["Source", "File", "Read", "Checked", "Stored", "Used by"];

test("shows six steps and a restricted one without content", async () => {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => url.startsWith("/api/v1/trail?kind=valuation&id=v1")
    ? json(200, { kind: "valuation", id: "v1", title: "Evergreen Growth I, valuation", figure: { label: "Evergreen Growth I", value: "10000000", currency: "USD" },
      steps: keys.map((k, i) => ({ key: k, label: labels[i], state: k === "file" ? "restricted" : "done", what: k === "file" ? "You do not have access to this step." : `${k} text`,
        who: k === "checked" ? "Mei Chen" : null, when: null, refs: [] })) })
    : json(404, {})));
  render(<MemoryRouter><ThemeProvider><SessionProvider><TrailPanel kind="valuation" id="v1" onClose={() => {}} /></SessionProvider></ThemeProvider></MemoryRouter>);
  expect(await screen.findByText(/1\. Source/)).toBeTruthy();
  expect(screen.getByText(/6\. Used by/)).toBeTruthy();
  expect(screen.getByText("Restricted")).toBeTruthy();
  expect(screen.getByText("You do not have access to this step.")).toBeTruthy();
  expect(screen.getByText("Mei Chen")).toBeTruthy();
});

test("links to the map only when a step carries a map id", async () => {
  const body = (refs: { kind: string; id: string; label: string }[]) => ({ kind: "valuation", id: "v1", title: "T", figure: null,
    steps: [{ key: "source", label: "Source", state: "done", what: "x", who: null, when: null, refs }] });
  const run = async (refs: { kind: string; id: string; label: string }[]) => {
    vi.stubGlobal("fetch", vi.fn(async () => json(200, body(refs))));
    render(<MemoryRouter><ThemeProvider><SessionProvider><TrailPanel kind="valuation" id="v1" onClose={() => {}} /></SessionProvider></ThemeProvider></MemoryRouter>);
    await screen.findByText(/1\. Source/);
  };
  await run([{ kind: "document", id: "7", label: "d" }]);
  expect(screen.queryByRole("link", { name: "Open in the map" })).toBeNull();
});

test("opens the flow tab on a source id", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => json(200, { kind: "valuation", id: "v1", title: "T", figure: null,
    steps: [{ key: "source", label: "Source", state: "done", what: "x", who: null, when: null, refs: [{ kind: "node", id: "source:abc", label: "s" }] }] })));
  render(<MemoryRouter><ThemeProvider><SessionProvider><TrailPanel kind="valuation" id="v1" onClose={() => {}} /></SessionProvider></ThemeProvider></MemoryRouter>);
  expect((await screen.findByRole("link", { name: "Open in the map" })).getAttribute("href")).toBe("/centre/map?focus=source%3Aabc");
});

test("shows the figure with separators, not the stored digits, and the earlier value beside it", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => json(200, { kind: "case", id: "c1", title: "T", figure: { label: "Evergreen Growth I", value: "10180000", currency: "USD", was: "10000000.0000000000", was_label: "used in September investment report" },
    steps: [{ key: "source", label: "Source", state: "done", what: "x", who: null, when: null, refs: [] }] })));
  render(<MemoryRouter><ThemeProvider><SessionProvider><TrailPanel kind="case" id="c1" onClose={() => {}} /></SessionProvider></ThemeProvider></MemoryRouter>);
  expect(await screen.findByText("Evergreen Growth I: 10,180,000 USD (used in September investment report: 10,000,000 USD)")).toBeTruthy();
});

test("a negative cash figure keeps its sign and loses the trailing zeros", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => json(200, { kind: "cash", id: "w1", title: "Wire WIRE-20261008-B01, Entity B", figure: { label: "Wire WIRE-20261008-B01, Entity B", value: "-12400.00000000", currency: "USD" },
    steps: [{ key: "source", label: "Source", state: "done", what: "x", who: null, when: null, refs: [] }] })));
  render(<MemoryRouter><ThemeProvider><SessionProvider><TrailPanel kind="cash" id="w1" onClose={() => {}} /></SessionProvider></ThemeProvider></MemoryRouter>);
  expect(await screen.findByText("Wire WIRE-20261008-B01, Entity B: -12,400 USD")).toBeTruthy();
  expect(screen.queryByText(/12400\.0/)).toBeNull();
});
