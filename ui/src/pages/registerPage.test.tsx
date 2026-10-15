import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import { ThemeProvider } from "../theme";
import { SessionProvider } from "../useSession";
import RegisterPage from "./RegisterPage";

const json = (body: unknown) => new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
const sg = { by: "Ann", at: "2026-10-01" };
const row = (code: string, name: string, n: number) => ({
  code, name, kind: "measure", owner: "Ann", pipeline: null, source: code === "b" ? { name: "Too concentrated", kind: "problem", href: "/centre/intent/map/problem:p1" } : null, version: 1, href: `/centre/intent/map/measure:${code}`,
  signed: Object.fromEntries(["charter", "baseline", "blueprint", "uat", "release"].map((s, i) => [s, i < n ? sg : null])),
});

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => url === "/api/auth/me"
    ? json({ display_name: "Ann", company_id: "co-a", roles: ["company_admin"] })
    : json({ rows: [row("a", "Alpha", 5), row("b", "Beta", 2)] })));
});
afterEach(() => vi.unstubAllGlobals());
const show = () => render(<MemoryRouter><ThemeProvider><SessionProvider><RegisterPage /></SessionProvider></ThemeProvider></MemoryRouter>);

test("the table, the pills and the count line render", async () => {
  show();
  expect(await screen.findByText("Alpha")).toBeInTheDocument();
  expect(screen.getByText("0 signed intents, 2 measures aligned, 1 fully released")).toBeInTheDocument();
  expect(screen.getAllByText("Release")).toHaveLength(2);
  expect(screen.getAllByTitle(/Charter: Ann, 1 Oct 2026/)).toHaveLength(2);
});

test("the missing-a-stage filter narrows the rows", async () => {
  show();
  await screen.findByText("Alpha");
  await userEvent.click(screen.getByRole("button", { name: "Missing a stage" }));
  expect(screen.queryByText("Alpha")).not.toBeInTheDocument();
  expect(screen.getByText("Beta")).toBeInTheDocument();
});

test("each row shows the five signature pills with who and when on hover", async () => {
  show();
  await screen.findByText("Beta");
  const beta = screen.getByText("Beta").closest("tr")!;
  const pills = beta.querySelectorAll("[data-signed]");
  expect([...pills].map((p) => p.textContent)).toEqual(["Charter", "Baseline", "Blueprint", "UAT", "Release"]);
  expect(pills[1]?.getAttribute("title")).toBe("Baseline: Ann, 1 Oct 2026");
  expect(pills[2]?.getAttribute("title")).toBe("Blueprint: not signed yet");
  expect([...beta.querySelectorAll("a")].find((a) => a.textContent === "Open")?.getAttribute("href")).toBe("/centre/intent/map/measure:b");
});

test("a row links to the problem it came from, or says not linked", async () => {
  show();
  await screen.findByText("Beta");
  expect(screen.getByRole("link", { name: "Too concentrated" }).getAttribute("href")).toBe("/centre/intent/map/problem:p1");
  expect(screen.getByText("Not linked")).toBeInTheDocument();
});

test("PF2: the signed intent, its measures, rules and plans are listed with signer and date", async () => {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => url === "/api/auth/me"
    ? json({ display_name: "Ann", company_id: "co-a", roles: ["company_admin"] })
    : json({ rows: [], records: [
        { kind: "intent", name: "Monthly report", by: "Daniel Foo", at: "2026-10-02T17:30:00+00:00", of: null, href: "/centre/intent/i1" },
        { kind: "measure", name: "Cash by entity", by: "Daniel Foo", at: "2026-10-02T17:30:00+00:00", of: "Monthly report", href: "/centre/intent/i1" },
        { kind: "rule", name: "CASH_TOLERANCE, version 1", by: "Raj Patel", at: "2026-10-01", of: null, href: "/centre/settings/rules" },
        { kind: "plan", name: "Build plan for Monthly report, version 1", by: "Ann", at: null, of: null, href: "/centre/build/p/prj-1" },
      ] })));
  show();
  expect(await screen.findByText("Monthly report")).toBeInTheDocument();
  expect(screen.queryByText("Nothing has been signed yet.")).not.toBeInTheDocument();
  expect(screen.getByText("1 signed intent, 1 measure aligned, 0 fully released")).toBeInTheDocument();
  const intent = screen.getByText("Monthly report").closest("tr")!;
  expect(intent.textContent).toContain("Intent of work");
  expect(intent.textContent).toContain("Daniel Foo");
  expect(intent.textContent).toContain("3 Oct 2026"); // 17:30 UTC on 2 Oct is 3 Oct in Singapore, the company's zone
  expect(screen.getByText("In Monthly report")).toBeInTheDocument();
  expect(screen.getByText("CASH_TOLERANCE, version 1").closest("tr")!.textContent).toContain("1 Oct 2026");
  expect(screen.getByText("Build plan for Monthly report, version 1").closest("tr")!.textContent).toContain("Not available yet");
});
