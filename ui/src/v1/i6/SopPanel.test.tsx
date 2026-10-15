import { fireEvent, render, screen } from "@testing-library/react";

import { ThemeProvider } from "../../theme";
import SopPanel from "./SopPanel";

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

// The shape k8_sop.build() returns (tests/v1/test_k8.py builds the same record).
const SOP = {
  title: "Standard operating procedure: Month-end reporting", version: 2, signed: "Signed by Arjun Mehta (sponsor) on 2026-10-08.",
  purpose: "The family reads it on the fifth working day", scope: "Issue the monthly report.", roles: ["Operations", "Finance"], systems: ["Excel"],
  steps: [
    { n: 1, name: "Pull administrator file", who: "Operations", system: "Administrator portal", does: "", input: "Administrator portal", output: "NAV file",
      control: "Row count checked against the portal", exception: "Ask the administrator to resend", manual: false, handovers: [{ to_step: 2, what: "NAV file" }] },
    { n: 2, name: "Reconcile cash in a spreadsheet", who: "Finance", system: "Excel", does: "", input: "NAV file", output: "Cash sheet",
      control: "Not stated yet", exception: "Not stated yet", manual: true, handovers: [] },
  ],
  manual_steps: [2], controls: [], definitions: [], open_points: ["Step 2 (Reconcile cash in a spreadsheet): the control is not stated yet."],
};

afterEach(() => vi.unstubAllGlobals());

test("the download link points at the SOP route and the preview shows steps, the manual flag and open points", async () => {
  const urls: string[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string) => { urls.push(url); return json(200, SOP); }));
  render(<ThemeProvider><SopPanel iid="i1" /></ThemeProvider>);
  expect(screen.getByRole("link", { name: "Download the procedure" })).toHaveAttribute("href", "/api/v1/intents/i1/sop/download");
  fireEvent.click(screen.getByRole("button", { name: "Read the procedure here" }));
  expect(await screen.findByText("Pull administrator file")).toBeInTheDocument();
  expect(urls).toEqual(["/api/v1/intents/i1/sop"]);
  expect(screen.getByText("Manual: could be automated")).toBeInTheDocument();
  expect(screen.getByText(/Hand over to step 2: NAV file/)).toBeInTheDocument();
  expect(screen.getByText(/the control is not stated yet/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Hide the procedure" }));
  expect(screen.queryByText("Pull administrator file")).toBeNull();
});

test("a refusal is shown in plain words", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => json(409, { detail: { error: "not_signed", message: "The procedure can be written once the intent of work is signed." } })));
  render(<ThemeProvider><SopPanel iid="i1" /></ThemeProvider>);
  fireEvent.click(screen.getByRole("button", { name: "Read the procedure here" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(/once the intent of work is signed/);
});

test("a9.5: each step says where it is from: the signed process map", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => json(200, SOP)));
  render(<ThemeProvider><SopPanel iid="i1" /></ThemeProvider>);
  fireEvent.click(screen.getByRole("button", { name: "Read the procedure here" }));
  expect(await screen.findAllByText("Where is this from?")).toHaveLength(2);
  expect(screen.getByText(/Step 1 of the process map in this intent of work\. Signed by Arjun Mehta/)).toBeInTheDocument();
});

test("UC9-01, UC9-05: the procedure scrolls into view and carries the file's closing sections", async () => {
  const scroll = vi.fn();
  Element.prototype.scrollIntoView = scroll;
  vi.stubGlobal("fetch", vi.fn(async () => json(200, { ...SOP, controls: ["Access: Only the office sees entity figures."], definitions: ["NAV: assets less liabilities"], open_points: [] })));
  render(<ThemeProvider><SopPanel iid="i1" /></ThemeProvider>);
  fireEvent.click(screen.getByRole("button", { name: "Read the procedure here" }));
  expect(await screen.findByText("Pull administrator file")).toBeInTheDocument();
  expect(scroll).toHaveBeenCalled();
  for (const head of ["Scope.", "Systems.", "Manual steps flagged for automation", "Controls", "Definitions", "Open points"]) expect(screen.getByText(head)).toBeInTheDocument();
  expect(screen.getByText("2. Reconcile cash in a spreadsheet")).toBeInTheDocument();
  expect(screen.getByText("Access: Only the office sees entity figures.")).toBeInTheDocument();
  expect(screen.getByText("None")).toBeInTheDocument();
});
