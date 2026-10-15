import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import { setSessionExpiredHandler } from "../api/client";
import { SessionProvider } from "../useSession";
import MemoryPage from "./MemoryPage";

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const calls: string[] = [];
const item = (id: string, agent: string, text: string) => ({ id, agent, agent_name: agent.charAt(0).toUpperCase() + agent.slice(1), kind: "preference", text, sure: "said", at: "2026-10-01T09:00:00", source: {} });

function mock(roles: string[]) {
  calls.length = 0;
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    calls.push(url);
    if (url === "/api/auth/me") return json(200, { display_name: "Leo", company_id: "co-a", roles });
    if (url === "/api/v1/memory/company") return json(200, { items: [], may_edit: true });
    return json(200, { items: [item("m1", "span", "Prefers: short answers"), item("m2", "tally", "Prefers: bullets answers")] });
  }));
}
const open = () => render(<MemoryRouter><SessionProvider><MemoryPage /></SessionProvider></MemoryRouter>);
afterEach(() => { vi.unstubAllGlobals(); setSessionExpiredHandler(null); });

it("a10.1: one list of the agent memory, Tally included, and no second contradicting list", async () => {
  mock(["analyst"]); open();
  expect(await screen.findByText("Prefers: short answers")).toBeInTheDocument();
  expect(screen.getByText("Tally remembers")).toBeInTheDocument();
  expect(screen.queryByText(/remember nothing about you yet/)).toBeNull();
  expect(calls.some((u) => u.startsWith("/api/memory/"))).toBe(false);
  expect(screen.getByText("What North, Span, Lumen and Tally remember about you")).toBeInTheDocument();
});

it("a10.1: an analyst may open and change company memory", async () => {
  mock(["analyst"]); open();
  await userEvent.click(await screen.findByRole("tab", { name: "Company memory" }));
  expect(await screen.findByLabelText("Add a company note")).toBeInTheDocument();
});

it("a participant reads company memory but cannot add to it", async () => {
  mock(["participant"]); open();
  await userEvent.click(await screen.findByRole("tab", { name: "Company memory" }));
  expect(await screen.findByText("Nothing yet")).toBeInTheDocument();
  expect(screen.queryByLabelText("Add a company note")).toBeNull();
});
