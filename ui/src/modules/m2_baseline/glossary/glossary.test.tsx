import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { copy } from "../../../copy";
import type { Prov } from "../api";
import { m2Steps } from "../copy";
import { m2Gloss as t } from "./copy";
import GlossaryScreen from "./GlossaryScreen";
import type { GlossaryChange, GlossaryEntry, GlossaryText, GlossaryView } from "./glossaryApi";

// M2-E2 glossary screen: five states, existing versus new with a filter, a choice per entry, review, upload, downloads, read-only when signed.
// Family-office wording only.

const BID = "b".repeat(32);
const G = `/api/modules/m2_baseline/baselines/${BID}/glossary`;
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const calls: { method: string; url: string; body: unknown }[] = [];

const p = (value: string | null, mark: Prov["mark"] = "stated", by = "Sara Lim"): Prov => ({ value, mark, by, at: "2026-10-03T09:00:00+00:00", from: "the work list" });
function entry(id: string, term: string, change: GlossaryChange, over: Partial<GlossaryEntry> = {}, text: Partial<GlossaryText> = {}): GlossaryEntry {
  const now = over.business_definition?.value ?? "Capital calls we expect to pay.";
  return {
    kpi_id: id,
    change,
    business_definition: p(now),
    previous: p(change === "new" ? null : "Calls we pay.", change === "new" ? "unknown" : "stated"),
    assumption: change === "changed" ? "Lens kept the baseline's wording; your glossary words it differently." : "",
    source_document: change === "new" ? "" : "glossary.csv",
    reviewed: null,
    text: {
      term, aliases: "", definition: now, how_sure: "Stated by Sara Lim", previous: change === "new" ? "Not available yet" : "Calls we pay.", owner: "Sara Lim", frequency: "Not available yet",
      who: "Everyone in the company", personal: "No", change: change[0]!.toUpperCase() + change.slice(1), assumption: "", source: "", reviewed: "Not reviewed yet", decided_by: "Not decided yet", proposal: "", ...text,
    },
    ...over,
  };
}
const view = (over: Partial<GlossaryView> = {}): GlossaryView => ({
  baseline_id: BID, signed: false, lens_available: true, built: true, waiting: 0, provided: { title: "glossary.csv", filename: "glossary.csv", by: "Pat Owner", at: "2026-10-03T09:00:00+00:00", truncated: false },
  entries: [
    entry("k1", "Capital calls due", "unchanged"),
    entry("k2", "Net asset value", "changed", { matched_term: "Net asset value" }, { aliases: "NAV" }),
    entry("k3", "Investor count", "new", { business_definition: p(null, "unknown") }, { definition: "Not available yet" }),
  ],
  counts: { all: 3, changed: 1, new: 1, unchanged: 1, reviewed: 0 }, unmatched_terms: [{ term: "Vendor rating", definition: "How we score suppliers." }], ...over,
});

function serve(get: () => Response | Promise<Response>, extra?: (url: string, method: string) => Response | undefined) {
  calls.length = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      const method = init?.method ?? "GET";
      calls.push({ method, url, body: init?.body ? JSON.parse(String(init.body)) : undefined });
      if (url === G && method === "GET") return get();
      return extra?.(url, method) ?? json(404, {});
    }),
  );
}
const open = () =>
  render(
    <MemoryRouter initialEntries={[`/modules/m2_baseline/glossary/${BID}`]}>
      <Routes>
        <Route path="/modules/m2_baseline/glossary/:baselineId" element={<GlossaryScreen />} />
      </Routes>
    </MemoryRouter>,
  );
afterEach(() => vi.unstubAllGlobals());
const rowOf = (name: string) => within(screen.getByRole("rowheader", { name: new RegExp(name) }).closest("tr") as HTMLElement);

describe("the five screen states", () => {
  it("loading", () => {
    serve(() => new Promise<Response>(() => undefined));
    open();
    expect(screen.getByRole("status")).toHaveTextContent(copy.states.loading);
  });
  it("empty: says so and still offers to upload a glossary", async () => {
    serve(() => json(200, view({ built: false, entries: [], counts: { all: 0, changed: 0, new: 0, unchanged: 0, reviewed: 0 }, provided: null, unmatched_terms: [] })));
    open();
    expect(await screen.findByText(t.empty)).toBeInTheDocument();
    expect(screen.getByText(t.uploadTitle)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: t.build })).toBeEnabled();
  });
  it("error: plain words and a way to try again", async () => {
    serve(() => json(500, { error: "x" }));
    open();
    expect(await screen.findByRole("alert")).toHaveTextContent(copy.states.error);
    expect(screen.getByRole("button", { name: copy.states.retry })).toBeInTheDocument();
  });
  it("refused: this module is not part of the plan", async () => {
    serve(() => json(403, { error: "module_not_available", message: "x" }));
    open();
    expect(await screen.findByRole("alert")).toHaveTextContent(copy.states.refused);
    expect(screen.queryByRole("button", { name: t.build })).toBeNull();
  });
  it("populated", async () => {
    serve(() => json(200, view()));
    open();
    expect(await screen.findByRole("table")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: t.title })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: m2Steps.glossary }).className).toContain("active");
  });
});

describe("existing versus new", () => {
  it("shows both wordings side by side with what Lens assumed, and the two lists", async () => {
    serve(() => json(200, view()));
    open();
    await screen.findByRole("table");
    const nav = rowOf("Net asset value");
    expect(nav.getByText("Calls we pay.")).toBeInTheDocument();
    expect(nav.getByText(/Lens kept the baseline's wording/)).toBeInTheDocument();
    expect(nav.getByText(t.alsoCalled("NAV"))).toBeInTheDocument();
    expect(rowOf("Investor count").getByText(t.noPrevious)).toBeInTheDocument();
    expect(screen.getByText(t.provided("glossary.csv", "Pat Owner", "2026-10-03"))).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: t.unmatchedTitle })).toBeInTheDocument();
    expect(screen.getByText("Vendor rating")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: t.newTitle })).toBeInTheDocument();
    expect(screen.getAllByText("Investor count")).toHaveLength(2); // in the table and in the list of what is new
  });
  it("tells the organiser plainly when part of the glossary was kept restricted", async () => {
    serve(() => json(200, view({ restricted_kept: 2 })));
    open();
    expect(await screen.findByText("2 entries are not given to Lens because they describe restricted measures. You can still review them here.")).toBeInTheDocument();
  });
  it("says nothing about it when nothing was kept restricted or the person may not know", async () => {
    serve(() => json(200, view({ restricted_kept: 0 })));
    open();
    await screen.findByRole("table");
    expect(screen.queryByText(/not given to Lens/)).toBeNull();
  });
  it("filters: all, changed, new, unchanged", async () => {
    serve(() => json(200, view()));
    open();
    await screen.findByRole("table");
    const user = userEvent.setup();
    expect(screen.getByRole("button", { name: `${t.filters.all} (3)` })).toHaveAttribute("aria-pressed", "true");
    await user.click(screen.getByRole("button", { name: `${t.filters.changed} (1)` }));
    expect(screen.getByRole("rowheader", { name: /Net asset value/ })).toBeInTheDocument();
    expect(screen.queryByRole("rowheader", { name: /Capital calls due/ })).toBeNull();
    await user.click(screen.getByRole("button", { name: `${t.filters.new} (1)` }));
    expect(screen.getByRole("rowheader", { name: /Investor count/ })).toBeInTheDocument();
    expect(screen.queryByRole("rowheader", { name: /Net asset value/ })).toBeNull();
    await user.click(screen.getByRole("button", { name: `${t.filters.unchanged} (1)` }));
    expect(screen.getByRole("rowheader", { name: /Capital calls due/ })).toBeInTheDocument();
  });
  it("shows nothing about a measure the person may not see: no row, no stub", async () => {
    serve(() => json(200, view({ unmatched_terms: [] })));
    open();
    await screen.findByRole("table");
    expect(screen.queryByText(/restricted/i)).toBeNull();
    expect(screen.getAllByRole("rowheader")).toHaveLength(3);
    expect(screen.getByText(t.unmatchedNone)).toBeInTheDocument();
  });
});

describe("deciding and reviewing", () => {
  const after = view({ counts: { all: 3, changed: 1, new: 1, unchanged: 1, reviewed: 1 } });
  it("keep ours, keep the provided wording and edit each send the choice", async () => {
    serve(() => json(200, view()), (url, method) => (method === "PUT" ? json(200, after) : undefined));
    open();
    await screen.findByRole("table");
    const user = userEvent.setup();
    await user.click(rowOf("Net asset value").getByRole("button", { name: t.keepOurs }));
    await waitFor(() => expect(calls.at(-1)).toMatchObject({ method: "PUT", url: `${G}/entries/k2`, body: { choice: "ours" } }));
    await user.click(rowOf("Net asset value").getByRole("button", { name: t.keepProvided }));
    await waitFor(() => expect(calls.at(-1)?.body).toMatchObject({ choice: "provided" }));
    await user.click(rowOf("Net asset value").getByRole("button", { name: t.edit }));
    await user.clear(screen.getByLabelText(t.editLabel));
    await user.type(screen.getByLabelText(t.editLabel), "Fund value net of fees.");
    await user.click(screen.getByRole("button", { name: t.save }));
    await waitFor(() => expect(calls.at(-1)?.body).toEqual({ choice: "edited", text: "Fund value net of fees." }));
    expect(await screen.findByText(t.progress(1, 3))).toBeInTheDocument();
  });
  it("this is not the same thing sends the choice, and only where a term was matched", async () => {
    serve(() => json(200, view()), (_u, method) => (method === "PUT" ? json(200, view()) : undefined));
    open();
    await screen.findByRole("table");
    expect(rowOf("Investor count").queryByRole("button", { name: t.notSame })).toBeNull();
    await userEvent.setup().click(rowOf("Net asset value").getByRole("button", { name: t.notSame }));
    await waitFor(() => expect(calls.at(-1)).toMatchObject({ method: "PUT", url: `${G}/entries/k2`, body: { choice: "not_same" } }));
  });
  it("nothing to keep is not offered: no provided wording, no wording of ours", async () => {
    serve(() => json(200, view()));
    open();
    await screen.findByRole("table");
    expect(rowOf("Investor count").getByRole("button", { name: t.keepProvided })).toBeDisabled();
    expect(rowOf("Investor count").getByRole("button", { name: t.keepOurs })).toBeDisabled();
  });
  it("marks one entry reviewed, and all unchanged ones together", async () => {
    serve(() => json(200, view()), (_u, method) => (method === "POST" ? json(200, after) : undefined));
    open();
    await screen.findByRole("table");
    const user = userEvent.setup();
    await user.click(rowOf("Net asset value").getByRole("button", { name: t.markReviewed }));
    await waitFor(() => expect(calls.at(-1)).toMatchObject({ method: "POST", url: `${G}/entries/k2/review` }));
    await user.click(screen.getByRole("button", { name: t.reviewAllUnchanged }));
    await waitFor(() => expect(calls.at(-1)).toMatchObject({ method: "POST", url: `${G}/review-unchanged` }));
  });
  it("an error from the server is shown in its own plain words", async () => {
    serve(() => json(200, view()), (_u, method) => (method === "PUT" ? json(422, { error: "invalid", message: "There is no wording in this baseline to keep yet." }) : undefined));
    open();
    await screen.findByRole("table");
    await userEvent.setup().click(rowOf("Net asset value").getByRole("button", { name: t.keepOurs }));
    expect(await screen.findByRole("alert")).toHaveTextContent("There is no wording in this baseline to keep yet.");
  });
});

describe("a provided glossary and the downloads", () => {
  it("uploads the chosen file as text for Lens to compare", async () => {
    serve(() => json(200, view()), (url, method) => (url === `${G}/upload` && method === "POST" ? json(200, { ...view(), note: "Only the first rows of a long sheet could be read." }) : undefined));
    open();
    await screen.findByRole("table");
    const user = userEvent.setup();
    expect(screen.getByRole("button", { name: t.upload })).toBeDisabled();
    await user.upload(screen.getByLabelText(t.uploadLabel), new File(["Term,Definition\nCash buffer,Cash held back"], "glossary.csv", { type: "text/csv" }));
    await user.click(screen.getByRole("button", { name: t.upload }));
    await waitFor(() => expect(calls.at(-1)).toMatchObject({ method: "POST", url: `${G}/upload`, body: { filename: "glossary.csv", data: btoa("Term,Definition\nCash buffer,Cash held back") } }));
    expect(await screen.findByText(/Only the first rows/)).toBeInTheDocument();
  });
  it("the build button asks Lens to update", async () => {
    serve(() => json(200, view()), (url, method) => (url === `${G}/build` && method === "POST" ? json(200, { ...view(), lens_note: "Lens could not reach the model just now; these are the pack's suggestions." }) : undefined));
    open();
    await screen.findByRole("table");
    await userEvent.setup().click(screen.getByRole("button", { name: t.build }));
    expect(await screen.findByText(/Lens could not reach the model/)).toBeInTheDocument();
  });
  it("links the Excel file and the printable page", async () => {
    serve(() => json(200, view()));
    open();
    await screen.findByRole("table");
    expect(screen.getByRole("button", { name: t.downloadExcel })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: t.downloadPrint })).toBeInTheDocument();
  });
});

describe("a signed baseline", () => {
  it("shows the read-only banner and cannot be changed from here", async () => {
    serve(() => json(200, view({ signed: true })));
    open();
    await screen.findByRole("table");
    expect(screen.getByText(m2Steps.signed)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: t.build })).toBeDisabled();
    expect(screen.getByRole("button", { name: t.reviewAllUnchanged })).toBeDisabled();
    expect(rowOf("Net asset value").getByRole("button", { name: t.keepOurs })).toBeDisabled();
    expect(rowOf("Net asset value").getByRole("button", { name: t.edit })).toBeDisabled();
    expect(screen.getByRole("button", { name: t.downloadExcel })).toBeInTheDocument();
  });
});
