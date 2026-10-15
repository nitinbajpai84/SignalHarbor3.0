import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { ThemeProvider } from "../../theme";
import type { LayoutItem } from "../cxui/api";
import ChecksPanel from "./ChecksPanel";
import Inspector from "./Inspector";
import OptionsPanel from "./OptionsPanel";

// STUDIO2 F2: inspector, options and checks against mocked fetch (synthetic data).
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
type Call = { method: string; url: string; body?: Record<string, unknown> };
function mock(routes: (c: Call) => Response | null) {
  const calls: Call[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    const c = { method: init?.method ?? "GET", url, body: init?.body ? JSON.parse(String(init.body)) : undefined };
    calls.push(c);
    return routes(c) ?? json(404, {});
  }));
  return calls;
}
const D = "/api/v1/build/p/EV-1/studio/dash-1";
const item: LayoutItem = { id: "w1", kind: "line", tile: "t1", title: "Cash per day", text: "", row: 0, col: 0, size: "medium", reads: ["cash daily"] };
const studio = { library: { kinds: ["line", "bar", "note"], tables: [{ name: "cash_daily", label: "cash daily", columns: [{ name: "entity", type: "text" }, { name: "cash_usd", type: "number" }] }], lumen: [] } };
const wrap = (ui: React.ReactElement) => render(<ThemeProvider>{ui}</ThemeProvider>);

describe("Inspector", () => {
  it("patches the tile, duplicates and removes", async () => {
    const calls = mock((c) => (c.url === D ? json(200, studio) : c.method === "GET" ? null : json(200, { ok: true, step: 1 })));
    const changed = vi.fn();
    wrap(<Inspector pid="EV-1" did="dash-1" item={item} onChanged={changed} />);
    await waitFor(() => expect(screen.getByRole("option", { name: "Treemap (shares)" })).toBeInTheDocument());
    await userEvent.selectOptions(screen.getByLabelText("Shown as"), "waterfall");
    await waitFor(() => expect(calls.find((c) => c.method === "PATCH")?.body).toEqual({ kind: "waterfall" }));
    expect(calls.find((c) => c.method === "PATCH")?.url).toBe(`${D}/tiles/t1`);
    await userEvent.selectOptions(screen.getByLabelText("Split by"), "entity");
    await waitFor(() => expect(calls.filter((c) => c.method === "PATCH").pop()?.body).toEqual({ split: "entity" }));
    await userEvent.selectOptions(screen.getByLabelText("Only, column"), "entity");
    await userEvent.type(screen.getByLabelText("Only these values"), "Entity B, Holdings");
    await userEvent.tab();
    await waitFor(() => expect(calls.filter((c) => c.method === "PATCH").pop()?.body).toEqual({ only: { column: "entity", values: ["Entity B", "Holdings"] } }));
    await userEvent.click(screen.getByRole("button", { name: "Duplicate" }));
    await waitFor(() => expect(calls.some((c) => c.method === "POST" && c.url === `${D}/widgets/w1/duplicate`)).toBe(true));
    await userEvent.click(screen.getByRole("button", { name: "Remove" }));
    await waitFor(() => expect(calls.some((c) => c.method === "DELETE" && c.url === `${D}/widgets/w1`)).toBe(true));
    expect(changed).toHaveBeenCalledTimes(5);
  });
  it("says so when a change is refused", async () => {
    mock((c) => (c.url === D ? json(200, studio) : c.method === "PATCH" ? json(400, { message: "That column is not in the table." }) : null));
    wrap(<Inspector pid="EV-1" did="dash-1" item={item} onChanged={() => undefined} />);
    await userEvent.selectOptions(screen.getByLabelText("Shown as"), "bar");
    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });
});

describe("OptionsPanel", () => {
  it("shows three options, marks the pick, and applies one", async () => {
    const opts = [
      { label: "Lines by entity", why: "Best for the trend.", patch: { kind: "line" }, pick: true },
      { label: "Bar per entity", why: "Best for now.", patch: { kind: "bar" }, pick: false },
      { label: "Table", why: "Best for exact figures.", patch: { kind: "table" }, pick: false },
    ];
    const calls = mock((c) => (c.url === `${D}/tiles/t1/options` ? json(200, { options: opts }) : c.method === "PATCH" ? json(200, { ok: true, step: 2 }) : null));
    const changed = vi.fn();
    wrap(<OptionsPanel pid="EV-1" did="dash-1" tid="t1" onChanged={changed} />);
    expect(await screen.findByText("Lines by entity")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /Use this/ })).toHaveLength(3);
    expect(screen.getByText(/Lumen's pick/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Use this: Bar per entity" }));
    await waitFor(() => expect(changed).toHaveBeenCalled());
    expect(calls.find((c) => c.method === "PATCH")?.body).toEqual({ kind: "bar" });
  });
});

describe("ChecksPanel", () => {
  it("lists checks and applies a fix", async () => {
    let fixed = false;
    const calls = mock((c) => {
      if (c.url === `${D}/checks`) return json(200, { checks: fixed ? [] : [{ id: "c1", widget: "t1", kind: "counted_twice", message: "Cash per day stacks two views of the same cash.", fix: { label: "Show side by side", patch: { kind: "bar" } } }] });
      if (c.method === "PATCH") { fixed = true; return json(200, { ok: true, step: 3 }); }
      return null;
    });
    const changed = vi.fn();
    wrap(<ChecksPanel pid="EV-1" did="dash-1" onChanged={changed} />);
    expect(await screen.findByText(/stacks two views/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Show side by side" }));
    await waitFor(() => expect(screen.getByText("Nothing to fix.")).toBeInTheDocument());
    expect(calls.find((c) => c.method === "PATCH")).toMatchObject({ url: `${D}/tiles/t1`, body: { kind: "bar" } });
    expect(changed).toHaveBeenCalled();
  });
});
