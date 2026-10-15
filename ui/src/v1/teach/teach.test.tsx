import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import { settingsFor, teachable } from "../../shell/roles";
import { ThemeProvider } from "../../theme";
import { SessionProvider } from "../../useSession";
import KnowledgePage from "./KnowledgePage";
import UsedLine from "./UsedLine";

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
afterEach(() => vi.unstubAllGlobals());
vi.setConfig({ testTimeout: 20000 });

const item = (over: Record<string, unknown> = {}) => ({ id: "kn_1", agent: "span", title: "Month end checks", kind: "file", name: "checks.md", size: 200, taught_by: "Leo Park",
  taught_at: "2026-10-12T08:30:00+00:00", active: true, version: 1, ...over });

function mock(roles: string[], sent: string[], items: Record<string, unknown[]> = { span: [item()], tally: [] }) {
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (url === "/api/auth/me") return json(200, { display_name: "Anita Rao", company_id: "evergreen", roles });
    if (init?.method && init.method !== "GET") {
      sent.push(`${init.method} ${url} ${String(init.body)}`);
      return json(200, item({ version: init.method === "PUT" ? 2 : 1, active: !url.endsWith("/active") || JSON.parse(String(init.body)).active }));
    }
    const m = /^\/api\/v1\/knowledge\/(\w+)$/.exec(url);
    if (m) return json(200, { agent: m[1], items: items[m[1] ?? ""] ?? [] });
    return json(404, { error: "not_found", message: "Not found." });
  }));
}
const show = (path = "/centre/settings/teach") => render(<MemoryRouter initialEntries={[path]}><ThemeProvider><SessionProvider><KnowledgePage /></SessionProvider></ThemeProvider></MemoryRouter>);

test("each person is offered only the agents they may teach", () => {
  expect(teachable(["analyst"])).toEqual(["span"]);                         // the data engineer
  expect(teachable(["analyst", "head_of_data"])).toEqual(["span", "lumen"]); // the head of data
  expect(teachable(["owner"])).toEqual(["tally", "lumen"]);                 // the business owner
  expect(teachable(["approver"])).toEqual(["tally"]);
  expect(teachable(["participant"])).toEqual([]);
  expect(teachable(["company_admin"])).toEqual(["span", "north", "tally", "lumen"]);
  expect(settingsFor(["analyst"]).has("teach")).toBe(true);
  expect(settingsFor(["participant"]).has("teach")).toBe(false);
});

test("the list shows who taught each item and when, and the page offers Span to a head of data", async () => {
  mock(["analyst", "head_of_data"], []);
  show();
  expect(await screen.findByRole("heading", { name: "Teach Span" })).toBeInTheDocument();
  const row = within(await screen.findByRole("table", { name: "What Span has been taught" })).getByText("Month end checks").closest("tr")!;
  expect(within(row).getByText("Leo Park")).toBeInTheDocument();
  expect(within(row).getByText("On")).toBeInTheDocument();
  expect(within(screen.getByRole("navigation", { name: "Agent to teach" })).getAllByRole("button").map((b) => b.textContent)).toEqual(["Span", "Lumen"]);
  expect(screen.queryByRole("button", { name: "Tally" })).toBeNull();
});

test("a note is taught with a title, and an item is switched off and replaced", async () => {
  const sent: string[] = [];
  mock(["analyst", "head_of_data"], sent);
  const user = userEvent.setup();
  show();
  await screen.findByRole("table", { name: "What Span has been taught" });
  expect(screen.getByRole("button", { name: "Teach Span" })).toBeDisabled();
  await user.type(screen.getByLabelText("Title"), "Close calendar");
  await user.type(screen.getByLabelText("Note"), "The close runs on working day three.");
  await user.click(screen.getByRole("button", { name: "Teach Span" }));
  await waitFor(() => expect(sent).toContain('POST /api/v1/knowledge/span {"title":"Close calendar","text":"The close runs on working day three."}'));
  await user.click(screen.getByRole("button", { name: "Switch off Month end checks" }));
  await waitFor(() => expect(sent).toContain('POST /api/v1/knowledge/span/kn_1/active {"active":false}'));
  await user.click(screen.getByRole("button", { name: "Replace Month end checks" }));
  const form = screen.getByRole("form", { name: "Replace Month end checks" });
  await user.type(within(form).getByLabelText("New note"), "New checks.");
  await user.click(within(form).getByRole("button", { name: "Save new version of Month end checks" }));
  await waitFor(() => expect(sent.some((s) => s.startsWith("PUT /api/v1/knowledge/span/kn_1 "))).toBe(true));
});

test("several books are taught at once, each titled after its file", async () => {
  const sent: string[] = [];
  mock(["analyst", "head_of_data"], sent);
  const user = userEvent.setup();
  show();
  await screen.findByRole("table", { name: "What Span has been taught" });
  await user.upload(screen.getByLabelText("Files"), [new File(["Facts and dimensions."], "Kimball Toolkit.txt", { type: "text/plain" }), new File(["Hubs and links."], "Data Vault.md", { type: "text/markdown" })]);
  expect(screen.getByLabelText("Title")).toBeDisabled();
  await user.click(screen.getByRole("button", { name: "Teach Span 2 files" }));
  await waitFor(() => expect(sent.filter((s) => s.startsWith("POST /api/v1/knowledge/span ")).length).toBe(2));
  expect(sent[0]).toContain('"title":"Kimball Toolkit","name":"Kimball Toolkit.txt"');
  expect(sent[1]).toContain('"title":"Data Vault","name":"Data Vault.md"');
  expect(await screen.findByText("Taught 2 of 2 files.")).toBeInTheDocument();
});

test("the owner is offered Tally and Lumen, and the link from Ask Tally opens Tally", async () => {
  mock(["owner"], [], { tally: [], lumen: [] });
  show("/centre/settings/teach?agent=tally");
  expect(await screen.findByRole("heading", { name: "Teach Tally" })).toBeInTheDocument();
  expect(await screen.findByText("Tally has not been taught anything yet.")).toBeInTheDocument();
});

test("a refusal from the server is shown in plain words", async () => {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => url === "/api/auth/me" ? json(200, { display_name: "Leo", company_id: "evergreen", roles: ["analyst"] })
    : json(403, { error: "not_allowed", message: "You cannot teach Span. Ask your administrator." })));
  show();
  expect(await screen.findByRole("alert")).toHaveTextContent("You cannot teach Span. Ask your administrator.");
});

test("a person who teaches nobody sees nothing to do", async () => {
  mock(["participant"], []);
  show();
  expect(await screen.findByText("You do not teach any of the agents.")).toBeInTheDocument();
});

test("the Used line names the passages, and is empty when nothing was used", () => {
  const { container, rerender } = render(<UsedLine used={[{ id: "kn_1", title: "Month end checks", passage: 2, line: "" }, { id: "kn_2", title: "Close calendar", passage: 1, line: "" }]} />);
  expect(screen.getByLabelText("Taught knowledge used")).toHaveTextContent("Used: Month end checks, passage 2; Close calendar, passage 1");
  rerender(<UsedLine used={[]} />);
  expect(container).toBeEmptyDOMElement();
});
