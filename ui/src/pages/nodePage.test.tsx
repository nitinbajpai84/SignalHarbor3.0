import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { setSessionExpiredHandler } from "../api/client";
import NodePage from "./NodePage";

// SHAPES 10, with the Q3 fields: trail `detail`, definition {business, technical, process}, may_see_named, comment `line`. Synthetic data.
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const AT = "2026-09-22T09:00:00+00:00";
const NODE = {
  id: "measure:k1", type: "Measure", label: "Trust NAV", owner: "Olga Trustee", steward: "Dan Data", baseline_id: "b".repeat(32), may_see_named: 6,
  trail: [
    { step: "asked", label: "Treasury wall", detail: "Problem: late capital-call notices · 11 cards", ref: "problem:p1", by: "a participant", at: AT },
    { step: "defined", label: "Baseline, version 1", detail: "Signed by Mei Tan · 22 Sep", ref: "term:k1", by: "Mei Tan", at: AT },
    { step: "supplied", label: "Custodian system", detail: "Fields: nav_total, as_of", ref: "source:s1", by: "the baseline", at: AT },
    { step: "built", label: "Pipeline custodian_daily", detail: "Design signed by Dan Data · 3 commits", ref: "pipeline:c", by: "the record", at: AT },
    { step: "released", label: "Release Band 1 2026-09", detail: "UAT: Harvey Rowley · release: Mei Tan", ref: "release:r", by: "Mei Tan", at: AT },
  ],
  definition: { term: "Trust NAV", business: "the total net asset value of the family trust at month end", technical: "sum of nav_total on the last business day",
    process: "custodian export on day 2 · reconciled by Olga on day 3" },
  versions: [{ v: 1, what: "Drafted by Lens", by: "Lens", at: AT }, { v: 3, what: "FX check added to the process map", by: "Dan Data", at: AT }],
  commits: [{ id: "c1", when: AT, what: "first build from blueprint v1", by: "Builder" }],
};
const COMMENTS = [
  { id: "a1", kind: "ambiguity", text: "Dormant vehicles: which is right?", by: "Harvey Rowley", at: AT, state: "open", decided_by: null, answer: null, line: "Open · Olga to decide" },
  { id: "a2", kind: "comment", text: "Nobody told the trustees.", by: "Anonymous", at: AT, state: "answered", decided_by: "Olga Trustee", answer: "added to the release note", line: "Answered: added to the release note" },
];

function mock(mayDecide: boolean, calls: { url: string; body?: string }[] = []) {
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    calls.push({ url, body: init?.body as string | undefined });
    if (url.endsWith("/comments") && init?.method === "POST") return json(200, COMMENTS[0]);
    if (url.endsWith("/comments")) return json(200, { comments: COMMENTS, may_decide: mayDecide });
    return json(200, NODE);
  }));
}
const open = () => render(<MemoryRouter initialEntries={["/centre/intent/map/measure:k1"]}>
  <Routes><Route path="/centre/intent/map/:nodeId" element={<NodePage />} /></Routes></MemoryRouter>);

afterEach(() => { vi.unstubAllGlobals(); setSessionExpiredHandler(null); });

describe("Node page", () => {
  test("shows the five trail tiles, the definition and the side cards", async () => {
    mock(false);
    open();
    expect(await screen.findByText("Treasury wall")).toBeInTheDocument();
    for (const t of ["Problem: late capital-call notices · 11 cards", "Custodian system", "Fields: nav_total, as_of", "Pipeline custodian_daily", "UAT: Harvey Rowley · release: Mei Tan"])
      expect(screen.getByText(t)).toBeInTheDocument();
    expect(screen.getByText(/A measure · version 3 · owned by Olga Trustee · steward of the map: Dan Data · released September 2026/)).toBeInTheDocument();
    expect(screen.getByText("Definition (version 3, current)")).toBeInTheDocument();
    expect(screen.getByText(/the total net asset value of the family trust/)).toBeInTheDocument();
    expect(screen.getByText("Process map: custodian export on day 2 · reconciled by Olga on day 3")).toBeInTheDocument();
    expect(screen.getByText(/only to the people on the list: 6 named/)).toBeInTheDocument();
    expect(screen.getByText("Each one reaches Olga as something to decide")).toBeInTheDocument();
  });

  test("the owner sees the decide controls and a participant does not", async () => {
    mock(true);
    const owner = open();
    expect(await screen.findByRole("button", { name: "Answer" })).toBeInTheDocument();
    owner.unmount();
    mock(false);
    open();
    await screen.findByText(/Dormant vehicles/);
    expect(screen.queryByRole("button", { name: "Answer" })).toBeNull();
  });

  test("an anonymous comment shows Anonymous and no person", async () => {
    mock(false);
    open();
    const text = await screen.findByText(/Nobody told the trustees/);
    const row = text.closest(".ds-comment") as HTMLElement;
    expect(row.textContent).toContain("Anonymous");
    expect(row.querySelector(".ds-avatar")?.textContent).toBe("A");
  });

  test("Suggest a change posts the kind, the text and the anonymous flag", async () => {
    const calls: { url: string; body?: string }[] = [];
    mock(false, calls);
    open();
    fireEvent.click(await screen.findByRole("button", { name: "Suggest a change" }));
    fireEvent.change(screen.getByLabelText("Your suggestion"), { target: { value: "Add the FX check" } });
    fireEvent.click(screen.getByLabelText("Post without my name"));
    fireEvent.click(screen.getByRole("button", { name: "Post" }));
    await waitFor(() => expect(calls.some((c) => c.url.endsWith("/comments") && c.body)).toBe(true));
    expect(JSON.parse(calls.find((c) => c.body)!.body!)).toEqual({ kind: "suggestion", text: "Add the FX check", anonymous: true });
  });

  test("deciding reloads the node so a new version shows without a page reload", async () => {
    const calls: { url: string; body?: string }[] = [];
    mock(true, calls);
    open();
    fireEvent.click(await screen.findByRole("button", { name: "Answer" }));
    await waitFor(() => expect(calls.some((c) => c.url.endsWith("/decide"))).toBe(true));
    await waitFor(() => expect(calls.filter((c) => c.url.endsWith("/graph/node/measure%3Ak1")).length).toBe(2));
  });
});
