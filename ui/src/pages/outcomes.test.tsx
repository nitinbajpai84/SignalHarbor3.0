import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { setSessionExpiredHandler } from "../api/client";
import { ThemeProvider } from "../theme";
import { SessionProvider } from "../useSession";
import OutcomesPage from "./OutcomesPage";

// Outcomes page: five screen states. fetch is stubbed per route.

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const NONE = {
  headline: { days_file_to_match: null, days_card_to_report: null, stage: "Not started", definitions_unchanged: null, match: null, cards_first_five: null, files_read: null, interviews: null, drafts_accepted: null },
  modules: [{ module: "m1_intent", actions: null, free_text: null, minutes: null }, { module: "m2_baseline", actions: null, free_text: null, minutes: null }, { module: "m3_connect", actions: null, free_text: null, minutes: null }],
  funnel: { cards: 0, clusters: 0, measures: 0, owned: 0, matching: 0 },
};
const SOME = {
  headline: { days_file_to_match: 5, days_card_to_report: null, stage: "Define strategically", definitions_unchanged: { unchanged: 1, of: 2 }, match: { matches: 1, gap: 1, cannot: 0, not_yet: 1, restricted: 2 }, cards_first_five: 1.5, files_read: 9, interviews: null, drafts_accepted: 3 },
  modules: [{ module: "m1_intent", actions: 9, free_text: 2, minutes: 90 }, { module: "m2_baseline", actions: null, free_text: null, minutes: null }, { module: "m3_connect", actions: 8, free_text: 0, minutes: null }],
  funnel: { cards: 40, clusters: 10, measures: 8, owned: 4, matching: 1 },
};

function mock(o: { status?: number; body?: unknown; hold?: boolean }) {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    if (url === "/api/auth/me") return json(200, { display_name: "Ann", company_id: "co-a", roles: ["company_admin"] });
    if (url === "/api/company") return json(200, { company_id: "co-a", name: "Lakeside Test Co", industry: "family_office" });
    if (o.hold) return new Promise<Response>(() => undefined);
    return json(o.status ?? 200, o.body ?? {});
  }));
}
const open = () => render(<MemoryRouter><ThemeProvider><SessionProvider><OutcomesPage /></SessionProvider></ThemeProvider></MemoryRouter>);

afterEach(() => { vi.unstubAllGlobals(); setSessionExpiredHandler(null); });

describe("Outcomes page", () => {
  test("loading", async () => {
    mock({ hold: true });
    open();
    expect(await screen.findByRole("status")).toHaveTextContent("Loading");
  });

  test("empty: nothing measured says so, no zeros", async () => {
    mock({ body: NONE });
    open();
    expect(await screen.findByText(/Nothing has been measured yet/)).toBeInTheDocument();
  });

  test("error offers a retry", async () => {
    mock({ status: 500, body: { error: "x", message: "x" } });
    open();
    expect(await screen.findByRole("alert")).toHaveTextContent("could not be loaded");
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });

  test("refused", async () => {
    mock({ status: 403, body: { error: "forbidden", message: "x" } });
    open();
    expect(await screen.findByRole("alert")).toHaveTextContent("do not have access");
  });

  test("populated: tiles, targets beside the measured values, the funnel; a missing figure is Not available yet", async () => {
    mock({ body: SOME });
    open();
    expect(await screen.findByText("5 days")).toBeInTheDocument();
    expect(screen.getByText("1 of 2")).toBeInTheDocument();
    expect(screen.getByText("1 of 3")).toBeInTheDocument();
    expect(screen.getByText(/2 restricted, not counted/)).toBeInTheDocument();
    expect(screen.getByText("Now at: Define strategically")).toBeInTheDocument();
    expect(screen.getAllByText("Not available yet").length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText(/Measured: 9 actions · Target: about 9 actions · Before: 25 actions/)).toBeInTheDocument();
    expect(screen.getByText(/Measured: 8 actions · Target: 8 actions · Before: 14 actions/)).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Owned 4" })).toBeInTheDocument();
    expect(screen.queryByText("0 days")).toBeNull();
  });
});
