import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { barFor, canOps, centresFor, settingsFor } from "../../shell/roles";
import { ThemeProvider } from "../../theme";
import { SessionProvider } from "../../useSession";
import SettingsPage from "./SettingsPage";

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
afterEach(() => vi.unstubAllGlobals());
vi.setConfig({ testTimeout: 20000 });

// ROLE1 (12 Oct): the Evergreen people and what each sees in Settings. The server stays the real gate; these are the menus.
const PEOPLE: Record<string, string[]> = {
  "Daniel Foo (sponsor)": ["sponsor"], "Mei Chen (business owner)": ["owner"], "Raj Patel (approver)": ["approver"], "Sofia Reyes (participant)": ["participant"],
  "Anita Rao (head of data)": ["analyst", "head_of_data"], "Leo Park (data engineer, ops)": ["analyst"], "Grace Ong (administrator)": ["company_admin"],
};
const OWN = ["What the agents remember about you", "Testing or Real use", "Activity trail"];
const TEACH = "Teach the agents"; // TEACH1: everyone who may teach at least one agent (not the participant)
const WANT: Record<string, string[]> = {
  "Daniel Foo (sponsor)": [...OWN, TEACH], "Mei Chen (business owner)": [...OWN, TEACH], "Sofia Reyes (participant)": OWN,
  "Raj Patel (approver)": [...OWN, TEACH, "Rules"],
  "Anita Rao (head of data)": [...OWN, TEACH, "Rules", "Identifiers and other names", "Instruments and asset classes", "Sources and data model", "Cycle date"],
  "Leo Park (data engineer, ops)": [...OWN, TEACH, "Identifiers and other names", "Instruments and asset classes", "Sources and data model", "Connectors", "Jobs and events"],
};

function show(roles: string[], path = "/centre/settings") {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => url === "/api/auth/me" ? json(200, { display_name: "P", company_id: "evergreen", roles })
    : url.startsWith("/api/memory") ? json(200, { items: [] }) : json(200, {})));
  render(<MemoryRouter initialEntries={[path]}><ThemeProvider><SessionProvider><Routes>
    <Route path="/centre/settings" element={<SettingsPage />} /><Route path="/centre/settings/:section" element={<SettingsPage />} />
    <Route path="*" element={<p>Landed elsewhere</p>} /></Routes></SessionProvider></ThemeProvider></MemoryRouter>);
}

test.each(Object.keys(WANT))("%s sees exactly their Settings items", async (who) => {
  show(PEOPLE[who]!);
  const nav = await screen.findByRole("navigation", { name: "Settings" });
  expect(Array.from(nav.querySelectorAll("a")).map((a) => a.textContent).sort()).toEqual([...WANT[who]!].sort());
});

test("the administrator sees every item, including People and access", async () => {
  show(["company_admin"]);
  const nav = await screen.findByRole("navigation", { name: "Settings" });
  const names = Array.from(nav.querySelectorAll("a")).map((a) => a.textContent);
  for (const n of [...OWN, "People and access", "Intent admin", "Templates and skills", "Outside assistants", "Agent runs and cost", "Demo", "Connectors", "Cycle date", TEACH]) expect(names).toContain(n);
  expect(names).toHaveLength(18);
});

test("Mei (owner) is sent away from a data-team item", async () => {
  show(["owner"], "/centre/settings/connectors");
  expect(await screen.findByText("Landed elsewhere")).toBeInTheDocument();
});

test("Mei (owner) still reaches Action, Build (her intent), Consume and Map; no Operations", () => {
  expect(barFor(["owner"])).toEqual(["action", "build", "consume", "map"]);
  expect(centresFor(["owner"]).has("intent")).toBe(true);
  expect(canOps(["owner"])).toBe(false);
});

test("Operations is the data engineer's and the administrator's, not the head of data's", () => {
  expect(canOps(["analyst"])).toBe(true);
  expect(canOps(["company_admin"])).toBe(true);
  expect(canOps(["analyst", "head_of_data"])).toBe(false);
  expect(settingsFor(["super_admin"]).size).toBe(0);
});
