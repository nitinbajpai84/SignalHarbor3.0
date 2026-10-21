import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import PortalPage from "./PortalPage";

vi.mock("../../useSession", () => ({ useSession: () => ({ user: { display_name: "Sofia Reyes" } }) }));

const portal = {
  member: "Sofia Reyes",
  share: {
    member: "Sofia Reyes", currency: "USD", as_of: "2026-10-21", basis: "lookthrough", total: "25520000", note: "Your share follows the ownership chain.",
    lines: [{ entity: "Evergreen Holdings", code: "EG-HOLD", level: "full", value: "16400000", your_pct: "30", your_value: "4920000", via: ["EG-TRUST > EG-HOLD"], portfolios: [{ name: "Liquid book", value: "16400000" }] },
            { entity: "Evergreen Family Trust", code: "EG-TRUST", level: "summary", value: "41200000", your_pct: "50", your_value: "20600000", via: [] }],
  },
  note: { headline: "Your share is worth USD 25.52 million.", lines: ["Your share is worth USD 25.52 million.", "1 approval is waiting for you."], as_of: "2026-10-21", text: "" },
  documents: [{ id: "d1", title: "Letter for Sofia", kind: "trust letter", date: "2026-09-30" }],
  approvals: [{ id: "ap-1", title: "Approve the school fee distribution", detail: "", amount: "12000", currency: "USD", status: "pending", raised_by: "Raj Patel", raised: "2026-10-20T08:00:00Z" }],
};
const json = (b: unknown, status = 200) => new Response(JSON.stringify(b), { status, headers: { "Content-Type": "application/json" } });
afterEach(() => vi.unstubAllGlobals());
const page = (path = "/v3/portal") => render(<MemoryRouter initialEntries={[path]}><PortalPage /></MemoryRouter>);

test("shows my share, the note, documents and approvals", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => json(portal)));
  page();
  expect(await screen.findByText("Hello, Sofia")).toBeInTheDocument();
  expect(screen.getByText("Follows the ownership chain")).toBeInTheDocument();
  expect(screen.getByText("USD 25,520,000")).toBeInTheDocument();
  expect(screen.getByText(/Your 30.0% is/)).toBeInTheDocument();
  expect(screen.getByText("Summary")).toBeInTheDocument();
  expect(screen.getByText("Letter for Sofia")).toBeInTheDocument();
  expect(screen.getByText("1 waiting")).toBeInTheDocument();
});

test("approving posts the decision and shows it done", async () => {
  const f = vi.fn(async (u: string, init?: RequestInit) => (init?.method === "POST" ? json({ ...portal.approvals[0], status: "approved" }) : json(portal)));
  vi.stubGlobal("fetch", f);
  page();
  await userEvent.click(await screen.findByRole("button", { name: "Approve" }));
  expect(await screen.findByText("Approved")).toBeInTheDocument();
  expect(f.mock.calls.some((c) => String(c[0]).endsWith("/approvals/ap-1/decide"))).toBe(true);
});

test("the ask box posts the question and shows the answer", async () => {
  const f = vi.fn(async (u: string, init?: RequestInit) => (init?.method === "POST" ? json({ answer: "Your share is USD 25.52 million.", used: [] }) : json(portal)));
  vi.stubGlobal("fetch", f);
  page();
  await userEvent.type(await screen.findByLabelText("Your question"), "what is my share worth?");
  await userEvent.click(screen.getByRole("button", { name: "Ask" }));
  expect(await screen.findByText("Your share is USD 25.52 million.")).toBeInTheDocument();
});

test("a person who is not family gets the plain refusal and the preview names the member", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => json({ detail: { error: "not_allowed", message: "This page is for the family members of the office." } }, 403)));
  page();
  expect(await screen.findByText(/for the family members of the office/)).toBeInTheDocument();
});

test("the admin preview has no approve buttons", async () => {
  const f = vi.fn(async () => json(portal));
  vi.stubGlobal("fetch", f);
  page("/v3/portal?member=Sofia%20Reyes");
  await screen.findByText("Sofia Reyes's portal");
  expect(screen.queryByRole("button", { name: "Approve" })).toBeNull();
  await waitFor(() => expect(f.mock.calls.some((c) => String(c[0]).includes("/api/v3/portal?member=Sofia%20Reyes"))).toBe(true));
});
