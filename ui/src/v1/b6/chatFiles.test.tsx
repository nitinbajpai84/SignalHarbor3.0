import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { ThemeProvider } from "../../theme";
import { SessionProvider } from "../../useSession";
import BuildPage from "./BuildPage";

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
afterEach(() => vi.unstubAllGlobals());
vi.setConfig({ testTimeout: 20000 });

const sent: string[] = [];
const turns = [{ id: "t1", by: "person", name: "Anna", text: "Here is the notes file. (attached: notes.csv)", at: "2026-10-09T10:00:00Z" },
  { id: "t2", by: "span", name: "Span", text: "I have read notes.csv.", at: "2026-10-09T10:00:01Z" }];

function mock(failUpload = false) {
  sent.length = 0;
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (url === "/api/auth/me") return json(200, { display_name: "Anna", company_id: "evergreen", roles: ["analyst"] });
    if (init?.method === "POST") {
      sent.push(`${url} ${String(init.body)}`);
      if (url.endsWith("/chat/files")) return failUpload ? json(422, { error: "invalid", message: "Cannot accept .exe files here." }) : json(200, { name: "notes.csv", path: "library/files/x", kind: "sample" });
      return json(200, { turns, pending: [] });
    }
    if (url === "/api/v1/build/p/EV-1/plan") return json(200, { project_id: "EV-1", title: "Monthly", intent_signed: true, plan: null, state: null, can: {} });
    if (url.endsWith("/chat")) return json(200, { turns: sent.length >= 2 ? turns : [], pending: [] });
    if (url.endsWith("/runs")) return json(200, { runs: [] });
    return json(404, { error: "not_found", message: "Not found." });
  }));
}
const view = () => render(<MemoryRouter initialEntries={["/centre/build/p/EV-1"]}><ThemeProvider><SessionProvider><Routes>
  <Route path="/centre/build/p/:projectId" element={<BuildPage />} /></Routes></SessionProvider></ThemeProvider></MemoryRouter>);

test("a file dropped in the Span chat is stored, then named in the turn", async () => {
  mock();
  view();
  const form = await screen.findByRole("form", { name: "Message Span" });
  fireEvent.drop(form, { dataTransfer: { files: [new File(["a,b\n1,2"], "notes.csv", { type: "text/csv" })] } });
  fireEvent.change(screen.getByLabelText("Your message"), { target: { value: "Here is the notes file." } });
  fireEvent.click(screen.getByRole("button", { name: "Send" }));
  expect(await screen.findByText("I have read notes.csv.")).toBeInTheDocument();
  expect(sent).toEqual([`/api/v1/build/p/EV-1/chat/files ${JSON.stringify({ name: "notes.csv", data: btoa("a,b\n1,2") })}`,
    `/api/v1/build/p/EV-1/chat ${JSON.stringify({ text: "Here is the notes file.", files: ["notes.csv"] })}`]);
});

test("a refused file says why in words and the turn is not sent", async () => {
  mock(true);
  view();
  const form = await screen.findByRole("form", { name: "Message Span" });
  fireEvent.drop(form, { dataTransfer: { files: [new File(["x"], "notes.csv")] } });
  fireEvent.click(screen.getByRole("button", { name: "Send" }));
  expect((await screen.findAllByRole("alert")).map((a) => a.textContent).join(" ")).toContain("Cannot accept .exe files here.");
  await waitFor(() => expect(sent).toHaveLength(1));
});
