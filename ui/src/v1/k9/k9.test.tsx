import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import { ThemeProvider } from "../../theme";
import fixture from "./daily.fixture.json";
import DailyNumbers from "./DailyNumbers";

// The fixture is the real response of sh_platform/v1/k9_routes.py for the Evergreen story on 9 Oct 2026 (USD and SGD).
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
afterEach(() => vi.unstubAllGlobals());
vi.setConfig({ testTimeout: 20000 });

function mock(seen: string[], over?: Response) {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    seen.push(url);
    if (over) return over;
    const cur = new URL(url, "http://x").searchParams.get("currency") as "USD" | "SGD";
    return json(200, (fixture as Record<string, unknown>)[cur]);
  }));
}
const wrap = () => render(<MemoryRouter><ThemeProvider><DailyNumbers /></ThemeProvider></MemoryRouter>);

test("six figures with a status word and a change line, each asking where it is from", async () => {
  mock([]);
  wrap();
  const total = await screen.findByRole("article", { name: "Total value" });
  expect(within(total).getByText("USD 103.41M")).toBeInTheDocument();
  expect(within(total).getByText(/Evergreen Holdings/)).toBeInTheDocument();
  expect(screen.getAllByRole("article")).toHaveLength(6);
  const issued = screen.getByRole("article", { name: "Known now against the issued report" });
  expect(within(issued).getByText("USD 57.78M")).toBeInTheDocument();
  expect(within(issued).getByText(/\+USD 180,000 since the report of 3 Oct 2026/)).toBeInTheDocument();
  expect(within(issued).getByText("Revised")).toBeInTheDocument();
  const ret = screen.getByRole("article", { name: "Return for Sep 2026" });
  expect(within(ret).getByText("4.17%")).toBeInTheDocument();
  expect(within(ret).getByText(/Benchmark 2.71%, \+1.46 points/)).toBeInTheDocument();
  const lv = screen.getByRole("article", { name: "What moved the liquid book" });
  expect(within(lv).getAllByText(/Northwind Logistics/).length).toBeGreaterThan(0);
  expect(within(lv).getByRole("link", { name: "Why did this move" })).toHaveAttribute("href", "/centre/consume/office#why-moved");   // JUC1B-004
  expect(within(screen.getByRole("article", { name: "Markets this month" })).getByText("+3.50%")).toBeInTheDocument();
  const liq = screen.getByRole("article", { name: "Cash after confirmed calls" });
  expect(within(liq).getByText(/USD 430,400 \(1 call not confirmed\)/)).toBeInTheDocument();
  expect(screen.getAllByRole("button", { name: /Where is this from\?/ })).toHaveLength(6);
});

test("where is this from opens the explanation and the records behind the figure", async () => {
  mock([]);
  wrap();
  await screen.findByRole("article", { name: "Total value" });
  await userEvent.click(screen.getByRole("button", { name: "Total value: Where is this from?" }));
  expect(screen.getByText(/Latest value of every holding on 09 Oct 2026 in USD/)).toBeInTheDocument();
});

test("the currency switch asks again in SGD and shows the converted report", async () => {
  const seen: string[] = [];
  mock(seen);
  wrap();
  await screen.findByRole("article", { name: "Total value" });
  await userEvent.click(screen.getByText("SGD"));
  await waitFor(() => expect(screen.getByText("SGD 77.49M")).toBeInTheDocument());
  expect(seen.map((u) => u.split("?")[1])).toEqual(["currency=USD", "currency=SGD"]);
});

test("a missing year to date return says why and never reads as zero", async () => {
  mock([]);
  wrap();
  await userEvent.click(await screen.findByText("SGD"));
  await waitFor(() => expect(screen.getByText(/no signed exchange rate for 31 Dec 2025/)).toBeInTheDocument());
});

test("an error reads as one plain sentence", async () => {
  mock([], json(503, { error: "unavailable", message: "The figures are not ready yet, so nothing is shown." }));
  wrap();
  expect(await screen.findByRole("alert")).toHaveTextContent("Something went wrong");
});

test("a section that could not be read says so and the other cards still show", async () => {
  const off = { available: false, message: "Not available yet." };
  vi.stubGlobal("fetch", vi.fn(async () => json(200, { ...(fixture as Record<string, Record<string, unknown>>).USD, nav: off, levers: off, markets: off })));
  wrap();
  const total = await screen.findByRole("article", { name: "Total value" });
  expect(within(total).getAllByText(/Not available yet/).length).toBeGreaterThan(0);
  expect(screen.getAllByRole("article")).toHaveLength(6);
  expect(screen.getByText("4.17%")).toBeInTheDocument();
});
