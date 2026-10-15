import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import { SessionProvider } from "../useSession";
import MarketPage from "./MarketPage";

const json = (body: unknown) => new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
const BRIEFS = [
  { id: "a", title: "Rates brief", summary: "Rates moved.", measures: ["K01"], source: "Demo pack", outside: true },
  { id: "b", title: "FX brief", summary: "FX moved.", measures: ["K02"], source: "Demo pack", outside: true },
];

const posts: unknown[] = [];
beforeEach(() => {
  posts.length = 0;
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (url === "/api/auth/me") return json({ display_name: "Ann", company_id: "co-a", roles: ["company_admin"] });
    if (url === "/api/company/market/briefs") { posts.push(JSON.parse(String(init?.body))); return json({}); }
    if (url === "/api/company/market") return json({ briefs: BRIEFS, internet: false, internet_line: "Internet is off for this company, so only the pack's briefs are shown." });
    if (url.endsWith("/walls")) return json({ walls: [] });
    return json({});
  }));
});
afterEach(() => vi.unstubAllGlobals());

const open = () => render(<MemoryRouter><SessionProvider><MarketPage /></SessionProvider></MemoryRouter>);

it("labels each brief as outside material and links its measures and Feeds", async () => {
  open();
  await screen.findByText("Rates brief");
  expect(screen.getAllByText("Outside material").length).toBeGreaterThanOrEqual(2);
  expect(screen.getByRole("link", { name: "K01" }).getAttribute("href")).toBe("/centre/intent/map/K01");
  expect(screen.getAllByRole("link", { name: "Feeds" })[0]!.getAttribute("href")).toBe("/centre/consume/feeds");
});

it("filters the briefs by measure", async () => {
  open();
  await screen.findByText("Rates brief");
  await userEvent.selectOptions(screen.getByLabelText("Measure"), "K02");
  expect(screen.queryByText("Rates brief")).toBeNull();
  expect(screen.getByText("FX brief")).toBeTruthy();
});

it("shows the internet line and lets the admin add a brief", async () => {
  open();
  await screen.findByText(/Internet is off for this company/);
  await userEvent.type(await screen.findByLabelText("Brief title"), "Our view");
  await userEvent.type(screen.getByLabelText("Brief text"), "Funding is tight.");
  await userEvent.type(screen.getByLabelText("Measure codes"), "K01, K02");
  await userEvent.click(screen.getByRole("button", { name: "Add brief" }));
  await vi.waitFor(() => expect(posts).toEqual([{ title: "Our view", text: "Funding is tight.", measures: ["K01", "K02"] }]));
});

it("shows the measures that moved as chips into the measure, and the Watch-lane card into its measure; no add form for the sponsor", async () => {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    if (url === "/api/auth/me") return json({ display_name: "Sam", company_id: "co-a", roles: ["sponsor"] });
    if (url === "/api/company/market") return json({ briefs: [{ ...BRIEFS[0], moved: [{ code: "K09", name: "Single-name concentration" }] }], internet: false, internet_line: "Internet is off." });
    if (url.endsWith("/walls")) return json({ walls: [{ id: "w1", state: "board" }] });
    if (url.includes("/w1")) return json({ clusters: [], on_its_own: [{ id: "n1", text: "A name above the limit, see K09", kind: "future_signal" }] });
    return json({});
  }));
  open();
  const chip = await screen.findByRole("link", { name: "Single-name concentration" });
  expect(chip.getAttribute("href")).toBe("/centre/consume/feeds/K09");
  const card = await screen.findByRole("link", { name: /A name above the limit/ });
  expect(card.getAttribute("href")).toBe("/centre/consume/feeds/K09");
  expect(screen.queryByLabelText("Brief title")).toBeNull();
});

it("a named measure with no feed move says Not available yet", async () => {
  open();
  await screen.findByText("Rates brief");
  expect(screen.getAllByText("Not available yet").length).toBe(2);
});
