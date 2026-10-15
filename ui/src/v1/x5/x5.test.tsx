import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import { setSessionExpiredHandler } from "../../api/client";
import ReviewPage from "./ReviewPage";

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const QUEUE = { count: 1, line: "1 document needs a look", items: [{ doc_id: "doc-stmt-abc123", file: "documents/stmt-08.md", type: "Custodian statement", intent_id: "i1", failed: [{ field: "total", kind: "present", why: "not found where it usually sits" }] }] };
const X = {
  doc_id: "doc-stmt-abc123", file: "documents/stmt-08.md", intent_id: "i1", type: "xt_1", type_name: "Custodian statement", version: 1, status: "review",
  values: { total: { value: "", raw: "", line: null, by: "rules" }, cash: { value: "310000", raw: "SGD 310,000", line: 2, by: "model" } },
  checks: [{ kind: "present", field: "total", detail: "", ok: false, why: "not found where it usually sits" }],
  lines: ["# Custodian statement", "| Securities | SGD 1,250,000 |", "| Cash | SGD 310,000 |", "| Portfolio value | SGD 1,560,000 |"],
};

afterEach(() => { vi.unstubAllGlobals(); setSessionExpiredHandler(null); });

it("shows a document that needs a look and accepts a corrected value", async () => {
  const posts: string[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method === "POST") { posts.push(`${url} ${String(init.body)}`); return json(200, { extraction: X, revision: null }); }
    return json(200, url.includes("/queue") ? QUEUE : X);
  }));
  render(<MemoryRouter><ReviewPage /></MemoryRouter>);
  expect(await screen.findByText("not found where it usually sits")).toBeInTheDocument();
  await userEvent.type(screen.getByLabelText("Value for total"), "1,560,000");
  await userEvent.click(screen.getByRole("button", { name: "Accept" }));
  expect(posts[0]).toContain("/api/v1/extract/doc-stmt-abc123/accept");
  expect(posts[0]).toContain('"values":{"total":"1,560,000"}');
});

it("refuses a viewer outside the data engineer seat", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => json(403, { error: "not_allowed", message: "Only the data engineer can do this." })));
  render(<MemoryRouter><ReviewPage /></MemoryRouter>);
  expect(await screen.findByText("The review queue is for the data engineer")).toBeInTheDocument();
});
