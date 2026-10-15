import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import type { KpiFull, WorkList } from "../api";
import { m2Work as W } from "../copy";
import OwnersPanel from "./OwnersPanel";

// Owner nomination: pick a person from the company's accounts (the account id is sent), or type a name for someone with no account.

const unknown = { value: null, mark: "unknown", by: "Lens", from: "", at: "2026-10-03T10:00:00+00:00" };
const kpi = { id: "K0", name: "Capital call timeliness", owners: { business: unknown, data: unknown, process: unknown }, missing_owners: ["business", "data", "process"] } as unknown as KpiFull;
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const bodies: unknown[] = [];

function setup(people: { account_id: string; display_name: string }[] | null) {
  bodies.length = 0;
  vi.stubGlobal("fetch", vi.fn(async (_url: string, init?: RequestInit) => {
    if ((init?.method ?? "GET") === "GET") return people ? json(200, { people }) : json(500, {});
    bodies.push(JSON.parse(String(init?.body)));
    return json(200, {});
  }));
  const act = vi.fn((p: Promise<WorkList>) => void p.catch(() => undefined));
  render(<OwnersPanel id="b1" kpi={kpi} me="" locked={false} act={act} />);
}
afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("nominating an owner", () => {
  test("picking an account sends its id, not a typed name", async () => {
    setup([{ account_id: "acct-mei", display_name: "Mei Tan" }]);
    const user = userEvent.setup();
    await screen.findAllByRole("option", { name: "Mei Tan" });
    await user.selectOptions(screen.getByLabelText(`${W.roles.business}: ${W.pickPerson}`), "acct-mei");
    await user.click(screen.getByRole("button", { name: `${W.nominate}: ${W.roles.business}` }));
    await waitFor(() => expect(bodies).toEqual([{ business: { account_id: "acct-mei" } }]));
  });

  test("a free name still works for someone with no account", async () => {
    setup([{ account_id: "acct-mei", display_name: "Mei Tan" }]);
    const user = userEvent.setup();
    await screen.findAllByRole("option", { name: "Mei Tan" });
    await user.type(screen.getByLabelText(`${W.roles.data}: ${W.ownerName}`), "Arjun Rao");
    await user.click(screen.getByRole("button", { name: `${W.nominate}: ${W.roles.data}` }));
    await waitFor(() => expect(bodies).toEqual([{ data: { name: "Arjun Rao", has_account: false } }]));
  });

  test("with no list of accounts only the name box shows", async () => {
    setup(null);
    await screen.findAllByRole("button", { name: new RegExp(W.nominate) });
    expect(screen.queryByLabelText(`${W.roles.business}: ${W.pickPerson}`)).toBeNull();
  });
});
