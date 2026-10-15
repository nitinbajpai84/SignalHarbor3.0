import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import CompanyPage, { type CompanyData } from "./CompanyPage";

const PAGE: CompanyData = {
  who: { name: { value: "Neera Family Office", by: "Arjun Mehta", at: "2026-10-07T10:00:00Z" } },
  systems: [{ id: "custodian", name: "Custodian daily files", kind: "feed", owner: "Kiran Iyer", lands: "CSV", frequency: "Daily" }],
  policies: [],
  documents: [{ doc_id: "01-ips.md", title: "01-ips.md", filename: "01-ips.md", uploaded_at: "2026-10-07T10:00:00Z" }],
  north_read_at: "2026-10-07T11:00:00Z",
  policy_kinds: ["access", "retention", "approval", "other"],
  accepted: ["md", "txt"],
  max_mb: 15,
  can_edit: true,
};
const calls: { method: string; body: unknown }[] = [];
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

function mock(page: Partial<CompanyData>, status = 200) {
  calls.length = 0;
  document.cookie = "sh_csrf=tok";
  vi.stubGlobal("fetch", vi.fn(async (_url: string, init?: RequestInit) => {
    const method = init?.method ?? "GET";
    const body = init?.body ? JSON.parse(String(init.body)) : undefined;
    calls.push({ method, body });
    if (status !== 200) return json(status, { error: "forbidden", message: "x" });
    return json(200, method === "PUT" ? { ...PAGE, ...page, policies: body.policies.map((p: object) => ({ ...p, stated_by: "Arjun Mehta" })) } : { ...PAGE, ...page });
  }));
}

afterEach(() => vi.unstubAllGlobals());

test("the decision maker adds a policy and saves", async () => {
  mock({});
  render(<CompanyPage />);
  expect(await screen.findByDisplayValue("Neera Family Office")).toBeInTheDocument();
  expect(screen.getByText(/North has read this/)).toBeInTheDocument();
  expect(screen.getByText("01-ips.md")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Add a policy" }));
  await userEvent.type(screen.getByLabelText("Policy 1"), "Keep statements seven years.");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  await waitFor(() => expect(screen.getByText("Saved.")).toBeInTheDocument());
  const put = calls.find((c) => c.method === "PUT")?.body as { policies: { kind: string; text: string }[] };
  expect(put.policies).toEqual([{ kind: "access", text: "Keep statements seven years." }]);
});

test("an analyst reads without edit boxes; a refusal says so", async () => {
  mock({ can_edit: false });
  const { unmount } = render(<CompanyPage />);
  expect(await screen.findByText("Neera Family Office")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Save" })).toBeNull();
  unmount();
  mock({}, 403);
  render(<CompanyPage />);
  expect(await screen.findByRole("alert")).toHaveTextContent("not open to your role");
});
