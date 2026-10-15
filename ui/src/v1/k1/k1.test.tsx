import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { ThemeProvider } from "../../theme";
import AccessPage from "./AccessPage";
import LockedRow from "./LockedRow";
import UploadStep from "./UploadStep";

// K1 screens against k1_routes (fetch stubbed, synthetic data): the upload step proposes Restricted for personal data and needs the
// owner's word to lower it; a locked row shows the preview and sends a request; the approve card answers.
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const calls: { method: string; url: string; body?: Record<string, unknown> }[] = [];
const stub = (routes: Record<string, unknown>) => vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
  calls.push({ method: init?.method ?? "GET", url, body: init?.body ? JSON.parse(String(init.body)) : undefined });
  const hit = routes[`${init?.method ?? "GET"} ${url}`];
  return hit === undefined ? json(404, {}) : json(200, hit);
}));
afterEach(() => { vi.unstubAllGlobals(); calls.length = 0; });

test("personal data proposes Restricted; lowering it needs the owner's word, and the choice is sent", async () => {
  stub({ "POST /api/v1/library/proposal": { sensitivity: "restricted", topics: ["Reporting"], by: "rules", topic_list: ["Reporting", "Finance"],
    pii: { found: true, kinds: ["email addresses"], where: ["column 4 (email)"] }, message: "Looks like reporting. Contains personal data (email addresses in column 4 (email)). Keep as Restricted?" } });
  const send = vi.fn(async () => ({ item: {} as never }));
  render(<ThemeProvider><UploadStep files={[{ file: new File(["x"], "clients.csv"), data: "eA==" }]} send={send} onDone={() => undefined} /></ThemeProvider>);
  expect(await screen.findByText(/Keep as Restricted\?/)).toBeInTheDocument();
  expect(screen.getByRole("radio", { name: /Restricted/ })).toHaveAttribute("aria-checked", "true");
  fireEvent.click(screen.getByRole("radio", { name: /Open/ }));
  const add = screen.getByRole("button", { name: "Add to the library" });
  expect(add).toBeDisabled();  // not personal data? say so first
  fireEvent.click(screen.getByLabelText(/not personal data/));
  fireEvent.click(add);
  await waitFor(() => expect(send).toHaveBeenCalled());
  expect(send.mock.calls[0]?.slice(1)).toEqual([{ sensitivity: "open", topic: ["Reporting"], reviewed: true }, false]);
});

test("three files in one go: each row has its own proposal and status, uploads run in order, a duplicate is named", async () => {
  stub({ "POST /api/v1/library/proposal": { sensitivity: "open", topics: ["Reporting"], by: "rules", topic_list: ["Reporting"],
    pii: { found: false, kinds: [], where: [] }, message: "Looks like reporting. No personal data found. Keep as Open?" } });
  const order: string[] = [];
  const send = vi.fn(async (file: File) => {
    order.push(file.name);
    if (file.name === "c.csv") return { duplicate: { id: "lib_1", name: "a.csv", uploaded_by: "Priya Nair", at: "2026-10-08" } };
    return file.name === "b.jpeg" ? { item: {} as never, message: "Stored. To read text from pictures this machine needs a picture reader; your company admin can switch it on." } : { item: {} as never };
  });
  const files = ["a.csv", "b.jpeg", "c.csv"].map((n) => ({ file: new File(["x"], n), data: "eA==" }));
  render(<ThemeProvider><UploadStep files={files} send={send} onDone={() => undefined} /></ThemeProvider>);
  const go = await screen.findByRole("button", { name: "Add 3 files to the library" });
  expect(screen.getAllByRole("radiogroup")).toHaveLength(3);
  fireEvent.click(go);
  expect(await screen.findByText(/c.csv is already in the library, uploaded by Priya Nair/)).toBeInTheDocument();
  expect(screen.getByText(/Stored. To read text from pictures/)).toBeInTheDocument();
  expect(screen.getAllByText("Added to the library.")).toHaveLength(1);
  expect(order).toEqual(["a.csv", "b.jpeg", "c.csv"]);
  expect(screen.queryByText(/could not look/i)).toBeNull();
});

test("a locked row shows the preview without values and sends a request", async () => {
  stub({ "POST /api/v1/library/lib_1/access": { id: "acc_1", state: "requested" } });
  render(<ThemeProvider><LockedRow iid="i1" item={{ id: "lib_1", name: "clients.csv", kind: "sample", size: 9, at: "2026-10-08", uploaded_by: "Arjun Mehta",
    sensitivity: "restricted", topic: ["Reporting"], access: "request", preview: { contains_personal_data: true, kinds: ["email addresses"] } }} /></ThemeProvider>);
  expect(screen.getByText(/Contains personal data: email addresses/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Request access to clients.csv" }));
  fireEvent.change(screen.getByLabelText("Why you need clients.csv"), { target: { value: "August reporting" } });
  fireEvent.click(screen.getByRole("button", { name: "Send request" }));
  expect(await screen.findByText(/waiting for Arjun Mehta/)).toBeInTheDocument();
  expect(calls[0]?.body).toEqual({ reason: "August reporting", iid: "i1" });
});

test("the approve card answers with one click", async () => {
  const req = { id: "acc_1", item_id: "lib_1", item_name: "custodian statements", requester: "Priya Nair", to: "Arjun Mehta", owner_left: false, reason: "", at: "2026-10-08", state: "requested", decided_by: null, decision_note: "", expires: null };
  stub({ "GET /api/v1/library/access": { incoming: [req], mine: [] }, "POST /api/v1/library/access/acc_1": { ...req, state: "granted" } });
  render(<ThemeProvider><MemoryRouter><AccessPage /></MemoryRouter></ThemeProvider>);
  expect(await screen.findByText(/Priya Nair asks to use custodian statements/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Approve" }));
  await waitFor(() => expect(calls.find((c) => c.method === "POST")?.body).toEqual({ approve: true, days: 30, note: "" }));
});
