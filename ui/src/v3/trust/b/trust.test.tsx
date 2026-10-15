import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactElement } from "react";
import { MemoryRouter } from "react-router-dom";

import ConnectionsPage from "../ConnectionsPage";
import PeoplePage from "../PeoplePage";
import ProofPage from "../ProofPage";
import WorkbenchPage from "../WorkbenchPage";

vi.mock("../../../useSession", () => ({ useSession: () => ({ user: { display_name: "Anita" } }) }));
afterEach(() => vi.unstubAllGlobals());
const json = (b: unknown, ok = true) => new Response(JSON.stringify(b), { status: ok ? 200 : 500, headers: { "Content-Type": "application/json" } });
const at = (ui: ReactElement, url = "/") => render(<MemoryRouter initialEntries={[url]}>{ui}</MemoryRouter>);

const people = { people: [{ name: "Anita", role: "decides" }], second_signer: false, autonomy: [{ thread: "Liquidity", level: "assist" }], ask_rules: [{ id: "r1", text: "Any money movement", on: true }], usage: { questions: 3, builds: 1, mode: "testing" } };

test("people: a level button posts the autonomy", async () => {
  const f = vi.fn(async (_u: string, i?: RequestInit) => json(i?.method === "POST" ? { ...people, autonomy: [{ thread: "Liquidity", level: "auto" }] } : people));
  vi.stubGlobal("fetch", f);
  at(<PeoplePage />);
  await userEvent.click(await screen.findByRole("button", { name: "Auto" }));
  await waitFor(() => expect(f.mock.calls.some((c) => String(c[0]).endsWith("/people/autonomy"))).toBe(true));
  await waitFor(() => expect(screen.getByRole("button", { name: "Auto" })).toHaveAttribute("aria-pressed", "true"));
});

test("people: error offers retry", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => json({}, false)));
  at(<PeoplePage />);
  expect(await screen.findByRole("button", { name: "Try again" })).toBeInTheDocument();
});

test("proof: lists runs and shows the empty state", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => json({ runs: [{ run_id: "RUN-1", thread: "t1", kind: "live", started: "9 Sep", files: 4, checks_passed: 11, checks_total: 12, result: "Ready", signed_by: "Anita" }] })));
  at(<ProofPage />);
  expect(await screen.findByText("RUN-1")).toBeInTheDocument();
  expect(screen.getByText("11/12")).toBeInTheDocument();
});

test("proof: empty", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => json({ runs: [] })));
  at(<ProofPage />);
  expect(await screen.findByText(/No runs yet/)).toBeInTheDocument();
});

test("workbench: no thread lists threads, a thread loads its bench", async () => {
  vi.stubGlobal("fetch", vi.fn(async (u: string) => json(String(u).endsWith("/threads") ? { threads: [{ id: "t1", title: "Liquidity", stage: "live", needs: 0 }] } : { steps: [{ n: 1, at: "", agent: "Span", action: "Read files", ok: true, detail: "" }], tables: [], rules: ["Ask first"] })));
  at(<WorkbenchPage />, "/v3/trust/workbench");
  expect(await screen.findByRole("link", { name: /Liquidity/ })).toHaveAttribute("href", "/v3/trust/workbench?thread=t1");
});

test("workbench: thread param", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => json({ steps: [{ n: 1, at: "", agent: "Span", action: "Read files", ok: true, detail: "" }], tables: [], rules: ["Ask first"] })));
  at(<WorkbenchPage />, "/v3/trust/workbench?thread=t1");
  expect(await screen.findByText("Read files")).toBeInTheDocument();
});

const conns = { connections: [{ id: "c1", kind: "sftp", name: "Administrator SFTP", target: "sftp.x.com", schedule: "daily", last_pull: "06:00", state: "failing" }] };

test("connections: cards, coming kinds disabled, add posts to the 2.0 route and clears secrets", async () => {
  const f = vi.fn(async (u: string, i?: RequestInit) => json(String(u).includes("/api/v1/") ? { ok: true, message: "Reached" } : conns, true, ));
  vi.stubGlobal("fetch", f);
  at(<ConnectionsPage />);
  expect(await screen.findByText("Administrator SFTP")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /Database/ })).toBeDisabled();
  await userEvent.click(screen.getByRole("button", { name: "SFTP" }));
  await userEvent.type(screen.getByLabelText(/^Name/), "office sftp");
  await userEvent.type(screen.getByLabelText(/^Source code/), "bank");
  await userEvent.type(screen.getByLabelText(/^User/), "CONN_U");
  expect(screen.getByLabelText(/^User/)).toHaveAttribute("type", "password");
  await userEvent.click(screen.getByRole("button", { name: "Save connection" }));
  await waitFor(() => expect(f.mock.calls.some((c) => String(c[0]) === "/api/v1/connectors/office-sftp" && c[1]?.method === "PUT")).toBe(true));
  await waitFor(() => expect(screen.getByLabelText(/^User/)).toHaveValue(""));
});

test("connections: empty", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => json({ connections: [] })));
  at(<ConnectionsPage />);
  expect(await screen.findByText(/No sources are connected yet/)).toBeInTheDocument();
});
