import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { ThemeProvider } from "../../theme";
import { SessionProvider } from "../../useSession";
import SignPage from "./SignPage";

// V6 design B3: the sponsor's own signing page. Everything on it comes from the I4 record and the project's people.
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
afterEach(() => vi.unstubAllGlobals());

const SOW = {
  id: "s", intent_id: "I1", title: "Monthly performance against benchmark", state: "draft", version: 1, signature: null, signatures: [],
  goal: { line: "A monthly page for the family council.", why: "To rebalance.", readers: ["The family council"], decisions: ["Do we rebalance?"], needed_by: "the 5th business day" },
  process: { steps: [{ n: 1, name: "Collect", who: "Mei", does: "Collects the files", inputs: [], outputs: [], system: "" }], handovers: [] },
  kpis: [{ code: "K1", name: "Return", definition: "Monthly return", formula: "end/start - 1", unit: "%", period: "month", owner: "Mei", source_ids: [], status: "defined", pack_suggested: false }],
  sources: [{ id: "a", name: "Administrator file", kind: "file", holds: "positions", sample_path: null, owner: "Leo", fields: [] }], catalogue: [], governance: [{ rule: "Show any change over 100,000", kind: "approval", applies_to: [], stated_by: "Daniel" }],
  unclear: [], may: { edit: true, sign: true, send_back: true }, sign_block: null, docx: false,
  before: { by: "Mei Chen", at: "2026-10-11T10:42:00", minutes: 14 },
};
const PROJECT = { id: "P1", intent_id: "I1", title: "x", started_by: "Mei Chen", started_at: "", stage: "talking", artefacts: [], people: { raiser: "Mei Chen", sponsor: null, builder: null, head_of_data: "Anita Rao", ops: null } };

function world(sent: string[], sow = SOW) {
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (url === "/api/auth/me") return json(200, { display_name: "Daniel Foo", account_id: "u-d", company_id: "evergreen", roles: ["sponsor"] });
    if (init?.method && init.method !== "GET") { sent.push(`${init.method} ${url} ${String(init.body ?? "")}`); return json(200, { ...sow, state: url.endsWith("/sign") ? "signed" : "draft", signature: url.endsWith("/sign") ? { name: "Daniel Foo", role: "sponsor", at: "2026-10-11T11:05:00Z" } : null }); }
    if (url === "/api/v1/intents/I1/sow") return json(200, sow);
    if (url === "/api/v1/intents/I1/project") return json(200, PROJECT);
    return json(404, { error: "not_found", message: "Not found." });
  }));
  return render(<MemoryRouter initialEntries={["/centre/intent/I1/sign"]}><ThemeProvider><SessionProvider><Routes><Route path="/centre/intent/:iid/sign" element={<SignPage />} /></Routes></SessionProvider></ThemeProvider></MemoryRouter>);
}

describe("the sign page", () => {
  test("says what is waiting, who finished it and when, and shows the intent in numbered sections", async () => {
    world([]);
    expect(await screen.findByRole("heading", { level: 1, name: "Sign the intent: Monthly performance against benchmark" })).toBeInTheDocument();
    expect(screen.getByText("WAITING FOR YOUR SIGNATURE")).toBeInTheDocument();
    expect(screen.getByText(/Before this: Mei Chen finished this with North on .* after 14 minutes\./)).toBeInTheDocument();
    expect(screen.getByText("Next: sign it, or send it back to Mei with a note.")).toBeInTheDocument();
    const doc = screen.getByRole("article", { name: "The intent of work" });
    expect(within(doc).getByText("Purpose")).toBeInTheDocument();
    expect(within(doc).getByText("Administrator file: positions")).toBeInTheDocument();
    expect(screen.getByText("Span drafts the design; Anita Rao approves it.")).toBeInTheDocument();
  });

  test("Sign needs the read box; the note goes with the signature; nothing is sent before", async () => {
    const sent: string[] = [];
    world(sent);
    const sign = await screen.findByRole("button", { name: "Sign intent" });
    expect(sign).toBeDisabled();
    await userEvent.click(screen.getByRole("checkbox", { name: /I have read all 7 sections/ }));
    await userEvent.type(screen.getByLabelText("Note to Mei (optional)"), "Please show the SGD view too.");
    expect(sent).toEqual([]);
    await userEvent.click(sign);
    await waitFor(() => expect(sent).toHaveLength(1));
    expect(sent[0]).toMatch(/^POST \/api\/v1\/intents\/I1\/sow\/sign /);
    expect(JSON.parse(sent[0]!.split(" ").slice(2).join(" "))).toEqual({ confirm: true, version: 1, note: "Please show the SGD view too." });
    expect(await screen.findByText(/Signed by Daniel Foo on .* Mei has been told and picks who builds it\./)).toBeInTheDocument();
  });

  test("Send back needs a note and goes to the send-back route", async () => {
    const sent: string[] = [];
    world(sent);
    const back = await screen.findByRole("button", { name: "Send back with a note" });
    expect(back).toBeDisabled();
    await userEvent.type(screen.getByLabelText("Note to Mei (optional)"), "Which benchmark version?");
    await userEvent.click(back);
    await waitFor(() => expect(sent).toHaveLength(1));
    expect(sent[0]).toMatch(/^POST \/api\/v1\/intents\/I1\/sow\/send-back /);
    expect(await screen.findByText("Sent back to Mei with your note.")).toBeInTheDocument();
  });

  test("a block the record names is shown and the person who may not sign cannot", async () => {
    world([], { ...SOW, sign_block: "Fill in the section: What the result looks like.", may: { edit: false, sign: false, send_back: false } } as never);
    await userEvent.click(await screen.findByRole("checkbox", { name: /I have read/ }));
    expect(screen.getByText("Fill in the section: What the result looks like.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sign intent" })).toBeDisabled();
  });
});
