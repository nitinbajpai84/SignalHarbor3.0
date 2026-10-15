import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import { ThemeProvider } from "../../theme";
import { SessionProvider } from "../../useSession";
import ConnectApiPage from "./ConnectApiPage";

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
afterEach(() => vi.unstubAllGlobals());
vi.setConfig({ testTimeout: 20000 });

const providers = [
  { id: "frankfurter", name: "Frankfurter (ECB reference rates)", host: "api.frankfurter.dev", blurb: "exchange rates, no key needed", needs_key: false, key_env: null, key_set: false,
    series: [{ id: "USD/SGD", label: "US dollar in Singapore dollars", kind: "fx" }, { id: "EUR/USD", label: "Euro in US dollars", kind: "fx" }] },
  { id: "fred", name: "FRED (St. Louis Fed)", host: "api.stlouisfed.org", blurb: "yields, free key", needs_key: true, key_env: "FRED_API_KEY", key_set: false,
    series: [{ id: "DGS10", label: "US 10-year Treasury yield, percent", kind: "yield" }] },
];

function mock(sent: string[], test: unknown = { ok: true, message: "Connected in 0.4 s. 2 series, up to 30 days each.", rows: [{ series: "USD/SGD", date: "2026-10-09", value: "1.2804" }, { series: "EUR/USD", date: "2026-10-09", value: "1.1200" }] }) {
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (url === "/api/auth/me") return json(200, { display_name: "Leo", company_id: "evergreen", roles: ["analyst"] });
    if (url === "/api/v1/connect-api/providers") return json(200, { providers, default_at: "05:30" });
    if (init?.method === "POST" || init?.method === "PUT") { sent.push(`${init.method} ${url} ${String(init.body ?? "")}`); return json(200, url.endsWith("/test") ? test : { id: "api-frankfurter" }); }
    return json(404, { error: "not_found", message: "Not found." });
  }));
}
const wrap = () => render(<MemoryRouter><ThemeProvider><SessionProvider><ConnectApiPage /></SessionProvider></ThemeProvider></MemoryRouter>);

test("test shows real rows with timing, and Save sends the provider and series only", async () => {
  const sent: string[] = [];
  mock(sent);
  wrap();
  await userEvent.click(await screen.findByRole("button", { name: "Test the connection" }));
  expect(await screen.findByText(/Connected in 0.4 s/)).toBeInTheDocument();
  expect(screen.getByText("1.2804")).toBeInTheDocument();
  expect(sent[0]).toBe('POST /api/v1/connect-api/test {"provider":"frankfurter","series":["USD/SGD","EUR/USD"]}');
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  expect(await screen.findByText(/every day at 05:30, before the 06:00 run/)).toBeInTheDocument();
  expect(sent[1]).toMatch(/^PUT \/api\/v1\/connectors\/api-frankfurter /);
  expect(sent[1]).not.toMatch(/key/i);
});

test("the key is named and never shown; a missing key is said plainly", async () => {
  mock([]);
  wrap();
  await userEvent.selectOptions(await screen.findByLabelText("Provider"), "fred");
  expect(screen.getByLabelText("Key")).toHaveValue("Stored by the administrator as FRED_API_KEY");
  expect(screen.getByText(/FRED_API_KEY is not set on the server yet/)).toBeInTheDocument();
});

test("a failed test says why", async () => {
  mock([], { ok: false, code: "internet_off", message: "Internet access is switched off for this module, so nothing was sent." });
  wrap();
  await userEvent.click(await screen.findByRole("button", { name: "Test the connection" }));
  expect(await screen.findByText(/Internet access is switched off/)).toBeInTheDocument();
});
