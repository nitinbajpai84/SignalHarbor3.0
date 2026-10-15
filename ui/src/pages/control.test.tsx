import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import App from "../App";
import { setSessionExpiredHandler } from "../api/client";

// IC-5b: the control panel, five states, role gating, a toggle calls its route, the log shows six columns and no payload. fetch is stubbed.

interface World { roles: string[]; hold?: boolean; fail?: number; entries?: Record<string, unknown>[]; requested?: boolean }
const calls: { method: string; url: string; body: unknown }[] = [];
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const ENTRY = { time: "2026-10-05T10:00:00Z", module: "m1", kind: "internet", host: "example.test", decision: "allowed", reason_code: "ok", bytes: 12 };

function mock(w: World) {
  calls.length = 0;
  document.cookie = "sh_csrf=tok";
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    const method = init?.method ?? "GET";
    calls.push({ method, url, body: init?.body ? JSON.parse(String(init.body)) : undefined });
    if (url === "/api/auth/me") return json(200, { display_name: "Ann", company_id: "co-a", roles: w.roles });
    if (url === "/api/company") return json(200, { company_id: "co-a", name: "Test Co", industry: "family_office" });
    if (url === "/api/modules") return json(200, []);
    if (url.startsWith("/api/control/") || url.startsWith("/api/company/")) {
      if (w.hold) return new Promise<Response>(() => undefined);
      if (w.fail) return json(w.fail, { error: w.fail === 403 ? "forbidden" : "x", message: "x" });
    }
    if (method === "PUT" && url.startsWith("/api/control/companies/")) return json(200, { on: true });
    if (method === "POST" && url === "/api/control/companies") return json(201, { id: "co-b", display: "Harbour House", industry: "family_office" });
    if (url === "/api/control/companies") return json(200, { companies: [{ id: "co-a", display: "Test Co", industry: "x", centres_on: ["intent"], modules_on: ["m1_intent"], email_domains: ["a.com"], accounts: { total: 3, active: 2 } }] });
    if (url === "/api/control/catalogue") return json(200, { modules: [{ id: "m1_intent", number: 1, name: "Intent", description: "", agent: "north" }], centres: [{ id: "intent", name: "Intent centre", description: "" }] });
    if (url === "/api/control/providers") return json(200, { allowed: {}, companies: { "co-a": { provider: "prov-one", model: "model-x" } } });
    if (url === "/api/company/settings" ) return json(200, { email_domains: ["a.com"], centres: ["intent"], egress: { internet: false, connectors: false, cloud_push: false, cloud_push_requested: !!w.requested } });
    if (method === "PUT" && url === "/api/company/settings/egress" && init?.body && String(init.body).includes("email_domains")) return json(200, { email_domains: ["b.org", "c.com"], centres: ["intent"], egress: { internet: false, connectors: false, cloud_push: false, cloud_push_requested: false } });
    if (method === "PUT" && url === "/api/company/settings/egress") return json(200, { centres: ["intent"], egress: { internet: true, connectors: false, cloud_push: false, cloud_push_requested: false } });
    if (url.startsWith("/api/company/egress-log")) return json(200, { entries: w.entries ?? [ENTRY] });
    return json(404, { error: "x", message: "x" });
  }));
}
const open = () => render(<MemoryRouter initialEntries={["/centre/control"]}><App /></MemoryRouter>);

afterEach(() => { vi.unstubAllGlobals(); setSessionExpiredHandler(null); });

describe("control panel", () => {
  test("loading", async () => {
    mock({ roles: ["company_admin"], hold: true });
    open();
    await userEvent.setup().click(await screen.findByRole("button", { name: "What may leave" }));
    expect(await screen.findByText("Loading...")).toBeInTheDocument();
  });
  test("error", async () => {
    mock({ roles: ["company_admin"], fail: 500 });
    open();
    await userEvent.setup().click(await screen.findByRole("button", { name: "What left" }));
    expect(await screen.findByText(/Something went wrong/)).toBeInTheDocument();
  });
  test("refused for a member", async () => {
    mock({ roles: ["member"] });
    open();
    expect(await screen.findByText(/not open to you/)).toBeInTheDocument();  // the role gate sends a member to the start page
    expect(screen.queryByText("THIS COMPANY")).toBeNull();
  });
  test("empty log", async () => {
    mock({ roles: ["company_admin"], entries: [] });
    open();
    await userEvent.setup().click(await screen.findByRole("button", { name: "What left" }));
    expect(await screen.findByText("Nothing has left yet. Each time an agent sends something out, it is listed here.")).toBeInTheDocument();
  });
  test("log: six columns, newest first as given, never a payload field", async () => {
    mock({ roles: ["company_admin"], entries: [{ ...ENTRY, payload_hash: "abc123", text: "secret words" }] });
    open();
    await userEvent.setup().click(await screen.findByRole("button", { name: "What left" }));
    const table = await screen.findByRole("table");
    expect(within(table).getAllByRole("columnheader")).toHaveLength(6);
    expect(table).toHaveTextContent("example.test");
    expect(document.body).not.toHaveTextContent("abc123");
    expect(document.body).not.toHaveTextContent("secret words");
    expect(screen.getByText("The log holds a fingerprint of what left, never the text.")).toBeInTheDocument();
  });
  test("company admin sees only this company; the gateway row is read only; a toggle calls its route", async () => {
    mock({ roles: ["company_admin"], requested: true });
    open();
    await userEvent.setup().click(await screen.findByRole("button", { name: "What may leave" }));
    expect(screen.queryByText("THE PLATFORM")).toBeNull();
    expect(screen.getByText("THIS PANEL HOLDS NO COMPANY DATA")).toBeInTheDocument();
    expect(await screen.findByRole("switch", { name: "Questions sent to the AI service" })).toBeDisabled();
    expect(screen.getByText(/requested/)).toBeInTheDocument();
    await userEvent.setup().click(screen.getByRole("switch", { name: "Internet for agents" }));
    await waitFor(() => expect(calls.some((c) => c.method === "PUT" && c.url === "/api/company/settings/egress" && JSON.stringify(c.body) === '{"internet":true}')).toBe(true));
  });
  test("super admin sees the control plane group, and a module switch calls its route", async () => {
    mock({ roles: ["super_admin"] });
    open();
    expect(await screen.findByText("THE PLATFORM")).toBeInTheDocument();
    expect(screen.queryByText("THIS COMPANY")).toBeNull();
    const u = userEvent.setup();
    expect(await screen.findByText("2 active of 3 accounts")).toBeInTheDocument();
    await u.click(screen.getByRole("button", { name: "Module catalogue" }));
    await u.click(screen.getByRole("button", { name: "Companies" }));
    await u.click(screen.getByRole("button", { name: "AI services" }));
    expect(await screen.findByText("prov-one model-x")).toBeInTheDocument();
  });
  test("super admin has no company group", async () => {
    mock({ roles: ["super_admin"] });
    open();
    await screen.findByText("THE PLATFORM");
    expect(screen.queryByRole("button", { name: "Centres and modules" })).toBeNull();
    await userEvent.setup().click(await screen.findByRole("switch", { name: "co-a m1_intent" }));
    expect(await screen.findByText("Saved.")).toBeInTheDocument();
    expect(screen.getByText("a.com")).toBeInTheDocument();
    await waitFor(() => expect(calls.some((c) => c.method === "PUT" && c.url === "/api/control/companies/co-a/modules/m1_intent" && JSON.stringify(c.body) === '{"on":false}')).toBe(true));
  });
  test("avatar menu offers the panel to admins only", async () => {
    mock({ roles: ["company_admin"] });
    open();
    await userEvent.setup().click(await screen.findByRole("button", { name: "Account menu" }));
    expect(screen.getByRole("link", { name: "Control panel" })).toBeInTheDocument();
  });
  test("rail: the super admin sees the control plane, the company header and creates a company", async () => {
    mock({ roles: ["super_admin"] });
    open();
    const rail = await screen.findByRole("navigation", { name: "Control panel sections" });
    expect(within(rail).getByText("THE PLATFORM")).toBeInTheDocument();
    expect(within(rail).getAllByRole("button").map((b) => b.textContent)).toEqual(["Companies", "Industry packs", "Module catalogue", "Agents and AI services", "AI services"]);
    expect(await screen.findByText(/Switches take effect the next time a page is opened./)).toBeInTheDocument();
    expect(screen.getByText("A centre that is off is invisible to the company: no pages, no agents, no tools.")).toBeInTheDocument();
    const u = userEvent.setup();
    await u.type(screen.getByLabelText("Short name"), "co-b");
    await u.type(screen.getByLabelText("Display name"), "Harbour House");
    await u.type(screen.getByLabelText("Industry pack"), "family_office");
    await u.click(screen.getByRole("button", { name: "Create company" }));
    await waitFor(() => expect(calls.some((c) => c.method === "POST" && c.url === "/api/control/companies"
      && JSON.stringify(c.body) === '{"id":"co-b","display":"Harbour House","industry":"family_office"}')).toBe(true));
  });
  test("rail: the company admin sees only THIS COMPANY and never calls the control plane", async () => {
    mock({ roles: ["company_admin"] });
    open();
    const rail = await screen.findByRole("navigation", { name: "Control panel sections" });
    expect(within(rail).getByText("THIS COMPANY")).toBeInTheDocument();
    expect(within(rail).queryByText("THE PLATFORM")).toBeNull();
    expect(within(rail).getAllByRole("button").map((b) => b.textContent)).toEqual(["Brand and people", "Centres and modules", "What may leave", "Retention", "What left"]);
    expect(await screen.findByText(/Test Co · Family office pack/)).toBeInTheDocument();
    expect(calls.some((c) => c.url.startsWith("/api/control/"))).toBe(false);
  });
  test("company admin edits the email domains on the overview and saves them", async () => {
    mock({ roles: ["company_admin"] });
    open();
    const box = await screen.findByLabelText("Email domains agents may write to");
    await waitFor(() => expect(box).toHaveValue("a.com"));
    const u = userEvent.setup();
    await u.clear(box);
    await u.type(box, "b.org, c.com");
    await u.click(screen.getByRole("button", { name: "Save domains" }));
    expect(await screen.findByText("Saved.")).toBeInTheDocument();
    expect(calls.find((c) => c.method === "PUT" && c.url === "/api/company/settings/egress")?.body).toEqual({ email_domains: ["b.org", "c.com"] });
  });
});
