import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import App from "../App";
import { setSessionExpiredHandler } from "../api/client";

// Home: tiles grouped under their centre's heading. fetch is stubbed.

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const tile = (id: string, number: number, name: string, extra: object = {}) => ({ id, number, name, description: `${name} d`, agent: "North", ...extra });
const INTENT = { centre: "intent", centre_name: "Intent centre", centre_description: "Agree what the business wants to know." };

function mock(modules: object[]) {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    if (url === "/api/auth/me") return json(200, { display_name: "Ann", company_id: "co-a", roles: ["analyst"] });
    if (url === "/api/company") return json(200, { company_id: "co-a", name: "Lakeside Test Co", industry: "family_office" });
    if (url === "/api/modules") return json(200, modules);
    return json(404, {});
  }));
}
const open = () => render(<MemoryRouter initialEntries={["/legacy"]}><App /></MemoryRouter>);

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  sessionStorage.clear();
  setSessionExpiredHandler(null);
});

test("tiles sit under the centre heading with its description", async () => {
  mock([tile("m1_intent", 1, "Intent", INTENT), tile("m2_baseline", 2, "Baseline", INTENT), tile("m4_build", 4, "Build", { centre: null })]);
  open();
  const heading = await screen.findByRole("heading", { name: "Intent centre" });
  expect(screen.getAllByRole("heading", { name: "Intent centre" })).toHaveLength(1);
  const section = heading.closest("section")!;
  expect(within(section).getByText("Agree what the business wants to know.")).toBeInTheDocument();
  expect(within(section).getAllByRole("link")).toHaveLength(2);
  expect(within(section).queryByText("Build")).toBeNull();
  expect(screen.getByText("Build")).toBeInTheDocument();
});

test("a centre switched off shows no heading and no tiles", async () => {
  mock([]);
  open();
  await screen.findByRole("heading", { name: /modules/i });
  expect(screen.queryByRole("heading", { name: "Intent centre" })).toBeNull();
  expect(screen.queryAllByRole("link", { name: /Intent/ })).toHaveLength(0);
});
