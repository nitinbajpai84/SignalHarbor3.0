import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { ThemeProvider } from "../../theme";
import { SessionProvider } from "../../useSession";
import SettingsPage from "./SettingsPage";

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
afterEach(() => vi.unstubAllGlobals());
vi.setConfig({ testTimeout: 20000 });

// Real shape of GET /api/v1/instruments (sh_platform/v1/e2c_routes.instrument_list).
const list = { asset_classes: ["hedge_fund", "listed_equity"], instruments: [
  { instrument_id: "kr", name: "Kestrel Ridge Macro Fund", instrument_type: "fund", asset_class: "hedge_fund", currency: "USD",
    names: [{ value: "KR Macro Fund Ltd - Class B USD", kind: "manager fund name", source: "Manager statements by email" }],
    codes: [{ value: "4481", kind: "administrator code", source: "Fund administrator" }] },
  { instrument_id: "prc", name: "Pacific Rim Convertible 2029 note", instrument_type: "convertible", asset_class: null, currency: "USD", names: [], codes: [] }] };

function show(path: string, roles: string[], sent: { url: string; body: unknown }[] = [], body: unknown = list) {
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (url === "/api/auth/me") return json(200, { display_name: "P", company_id: "evergreen", roles });
    if (init?.method === "POST") { sent.push({ url, body: JSON.parse(String(init.body)) }); return json(200, { ...list.instruments[1], asset_class: "listed_equity" }); }
    if (url === "/api/v1/instruments") return json(200, body);
    if (url === "/api/v1/rules") return json(200, []);
    return json(404, { error: "not_found", message: "Not found." });
  }));
  render(<MemoryRouter initialEntries={[path]}><ThemeProvider><SessionProvider><Routes>
    <Route path="/centre/settings/:section" element={<SettingsPage />} /><Route path="*" element={<p>Landed elsewhere</p>} /></Routes></SessionProvider></ThemeProvider></MemoryRouter>);
}

test("Settings > identifiers lists a fund's other name and its administrator code (P13)", async () => {
  show("/centre/settings/identifiers", ["analyst"]);
  expect(await screen.findByText(/KR Macro Fund Ltd - Class B USD/)).toBeInTheDocument();
  expect(screen.getByText(/4481 \(administrator code, Fund administrator\)/)).toBeInTheDocument();
});

test("Settings > identifiers names who follow-ups go to once the route sends contacts (AUC3-07, P11), and no column before", async () => {
  const cp = { instrument_id: "cp", name: "Cedarpoint Ventures III", instrument_type: "fund", asset_class: null, currency: "USD", names: [], codes: [],
    contacts: [{ value: "Hana Sato", kind: "manager contact", source: "Manager contacts" }] };
  show("/centre/settings/identifiers", ["company_admin"], [], { ...list, instruments: [...list.instruments.map((i) => ({ ...i, contacts: [] })), cp] });
  expect(await screen.findByRole("columnheader", { name: "Follow-ups go to" })).toBeInTheDocument();
  expect(screen.getByText("Hana Sato (manager contact, Manager contacts)")).toBeInTheDocument();
  expect(screen.getByText("Nobody named")).toBeInTheDocument();
});

test("Settings > identifiers shows no contact column while the route sends none", async () => {
  show("/centre/settings/identifiers", ["analyst"]);
  await screen.findByText(/4481/);
  expect(screen.queryByRole("columnheader", { name: "Follow-ups go to" })).toBeNull();
});

test("Settings > instruments gives the note without a class one (P19)", async () => {
  const sent: { url: string; body: unknown }[] = [];
  show("/centre/settings/instruments", ["company_admin"], sent);
  await userEvent.selectOptions(await screen.findByLabelText("Asset class for Pacific Rim Convertible 2029 note"), "listed_equity");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  expect(await screen.findByText(/is now listed equity/)).toBeInTheDocument();
  expect(sent).toEqual([{ url: "/api/v1/instruments/prc/asset-class", body: { asset_class: "listed_equity" } }]);
});

test("the approver opens Settings > Rules but no other admin section", async () => {
  show("/centre/settings/rules", ["approver"]);
  expect(await screen.findByRole("link", { name: "Rules" })).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "Identifiers and other names" })).toBeNull();
});

test("the approver is refused the identifiers section", async () => {
  show("/centre/settings/identifiers", ["approver"]);
  expect(await screen.findByText("Landed elsewhere")).toBeInTheDocument();
});
