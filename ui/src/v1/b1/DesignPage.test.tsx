import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { ThemeProvider } from "../../theme";
import { SessionProvider } from "../../useSession";
import DesignPage from "./DesignPage";

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const note = { lines: ["Landing keeps 1 tables exactly as they arrive from 2 sources."], fallback: true, message: "Span could not reach the model. This is the rule-based draft.", at: "2026-10-07T10:00:00+00:00", asked_by: "Leela Raman", blueprint_version: 1, record_version: 1, counts: { gold: 2 } };
const arch = { version: 1, regenerated: { moment: "sow_signed", by: "Span", at: "2026-10-07" }, counts: { data: 1, infrastructure: 0, enterprise: 0 }, versions: [{ v: 1, moment: "sow_signed", at: "2026-10-07" }],
  components: [{ id: "gold:twr", label: "gold.twr", kind: "gold", view: "data", owner: null, version: 1, state: "proposed" }], diagram: { components: [{ id: "gold:twr", label: "gold.twr" }], connections: [] } };

function mock(design: unknown, posts: string[]) {
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (url === "/api/auth/me") return json(200, { display_name: "Leela Raman", company_id: "neera", roles: ["analyst"] });
    if (init?.method === "POST") { posts.push(url); return json(200, note); }
    if (url.startsWith("/api/v1/build/")) return json(200, design);
    if (url.startsWith("/api/company/build/architecture")) return json(200, arch);
    return json(404, { message: "no" });
  }));
}
const wrap = () => render(<MemoryRouter initialEntries={["/centre/build/i1/design"]}><ThemeProvider><SessionProvider><Routes><Route path="/centre/build/:iid/design" element={<DesignPage />} /></Routes></SessionProvider></ThemeProvider></MemoryRouter>);
afterEach(() => vi.unstubAllGlobals());
vi.setConfig({ testTimeout: 20000 });

test("shows Span's labelled draft from the signed SOW and asks again", async () => {
  const posts: string[] = [];
  mock({ intent_id: "i1", sow_state: "signed", title: "Monthly pack", design: note, can_draft: true }, posts);
  wrap();
  expect(await screen.findByText(/Drafted by Span from the signed intent of work on/)).toBeInTheDocument();
  expect(screen.getByText(/rule-based draft/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Ask Span to draft again" }));
  expect(posts).toEqual(["/api/v1/build/i1/design"]);
});

test("an unsigned SOW: no design and no ask button", async () => {
  mock({ intent_id: "i1", sow_state: "draft", title: "Monthly pack", design: null, can_draft: false }, []);
  wrap();
  expect(await screen.findByText("The intent of work is not signed yet.")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /Ask Span/ })).toBeNull();
});
