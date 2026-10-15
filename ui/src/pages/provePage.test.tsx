import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import { setSessionExpiredHandler } from "../api/client";
import { ThemeProvider } from "../theme";
import { SessionProvider } from "../useSession";
import ProvePage from "./ProvePage";

const json = (b: unknown) => new Response(JSON.stringify(b), { status: 200, headers: { "Content-Type": "application/json" } });
const per = (period: string, result: string, reason: string | null) => ({ period, ours: 10, reported: result === "not_yet" ? null : 12, result, reason, accepted_by: null });
const DATA = {
  band: "A",
  measures: [
    { code: "nav", name: "Net asset value", tester: "Ann", periods: [per("2026-08", "match", null), per("2026-09", "gap", "Fee timing")], uat: { state: "pending" }, release_ready: false },
    { code: "cash", name: "Cash", periods: [per("2026-09", "not_yet", null)], uat: { state: "signed", by: "Ann" }, release_ready: true },
  ],
  release: { state: "draft", sponsor: "Ann" },
};
let calls: [string, string | undefined][] = [];
function mock() {
  calls = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    calls.push([url, init?.method]);
    if (url === "/api/auth/me") return json({ display_name: "Ann", company_id: "co", roles: ["company_admin"] });
    if (url === "/api/company") return json({ company_id: "co", name: "Test Co", industry: "family_office" });
    if (url === "/api/company/build/prove") return json(DATA);
    return json({});
  }));
}
const open = () => render(<MemoryRouter><ThemeProvider><SessionProvider><ProvePage /></SessionProvider></ThemeProvider></MemoryRouter>);
afterEach(() => { vi.unstubAllGlobals(); setSessionExpiredHandler(null); });

describe("Prove page", () => {
  test("table shows results and reasons", async () => {
    mock(); open();
    expect(await screen.findByText("Fee timing")).toBeInTheDocument();
    expect(screen.getByText("Gap")).toBeInTheDocument();
    expect(screen.getByText("Match")).toBeInTheDocument();
    expect(screen.getByText("Not yet")).toBeInTheDocument();
  });
  test("Sign UAT calls the route", async () => {
    mock(); open();
    fireEvent.click(await screen.findByRole("button", { name: "Sign UAT" }));
    await waitFor(() => expect(calls).toContainEqual(["/api/company/build/uat/nav/sign", "POST"]));
  });
  test("Sign UAT only for the named tester", async () => {
    mock(); DATA.measures[0]!.tester = "Bob";
    open();
    await screen.findByText("Fee timing");
    expect(screen.queryByRole("button", { name: "Sign UAT" })).toBeNull();
    DATA.measures[0]!.tester = "Ann";
  });
  test("the named tester signs UAT with a note; the sponsor alone releases", async () => {
    const saved = DATA.release;
    DATA.release = { state: "draft", sponsor: "Mei Tan" };
    calls = [];
    const bodies: string[] = [];
    vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
      calls.push([url, init?.method]);
      if (init?.body) bodies.push(String(init.body));
      if (url === "/api/auth/me") return json({ display_name: "Ann", company_id: "co", roles: ["analyst"] });
      if (url === "/api/company") return json({ company_id: "co", name: "Test Co", industry: "family_office" });
      return json(DATA);
    }));
    open();
    await userEvent.type(await screen.findByLabelText("UAT note for nav"), "checked against the pack");
    await userEvent.click(screen.getByRole("button", { name: "Sign UAT" }));
    await waitFor(() => expect(calls).toContainEqual(["/api/company/build/uat/nav/sign", "POST"]));
    expect(bodies.some((b) => b.includes("checked against the pack") && b.includes("signed"))).toBe(true);
    expect(screen.queryByRole("button", { name: "Sign the release" })).toBeNull();
    expect(screen.getByText(/Only Mei Tan, the sponsor, signs the release/)).toBeInTheDocument();
    expect(screen.getByText("Fee timing")).toHaveClass("ds-warn");
    DATA.release = saved;
  });

  test("release disabled and names what is missing", async () => {
    mock(); open();
    expect(await screen.findAllByText(/nav is not ready/)).not.toHaveLength(0);
    expect(screen.getByRole("button", { name: "Release 1 measure" })).toBeEnabled();
  });

  test("a signed partial release says who, when and how many are held back", async () => {
    const saved = DATA.release;
    DATA.release = { state: "signed", by: "Daniel Kerr", at: "2026-10-07T09:00:00+00:00", held_back: [{ code: "nav", reason: "waits for its figure" }] } as unknown as typeof DATA.release;
    mock(); open();
    expect(await screen.findByText(/Released by Daniel Kerr on 7 October 2026 · 1 held back/)).toBeInTheDocument();
    DATA.release = saved;
  });

  test("a flagged measure offers a re-check that needs a reason, and past re-checks are listed", async () => {
    const D = DATA as unknown as { measures: object[]; checks?: unknown };
    const saved = D.measures[1]!;
    D.checks = [{ version: 1, at: "2026-10-07T09:00:00+00:00", by: "Ann", reason: "Pack reloaded", changed: ["cash"], voided: [] }];
    D.measures[1] = { ...saved, changed: ["2026-09"] };
    mock(); open();
    const btn = await screen.findByRole("button", { name: "Re-check figures" });
    expect(btn).toBeDisabled();
    expect(screen.getByText(/Ann, 7 October 2026: Pack reloaded. Changed: cash/)).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("Reason to re-check cash"), "FX11 check");
    await userEvent.click(btn);
    await waitFor(() => expect(calls).toContainEqual(["/api/company/build/prove/recheck", "POST"]));
    D.measures[1] = saved;
    delete D.checks;
  });
});
