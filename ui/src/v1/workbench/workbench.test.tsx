import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { ThemeProvider } from "../../theme";
import Workbench from "./Workbench";

// L1: the strip (enlarge, Esc, close, reopen, pin, remembered layout) and the chat footer's attach menu; fetch stubbed, synthetic data.
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const item = (id: string, name: string) => ({
  id, name, kind: "document", note: "", uploaded_by: "Seeded", at: "2026-10-08T09:00:00Z", size: 10, visibility: "company",
  path: `documents/${name}`, tags: [], mine: false, can_change: false,
});
const DOCS = ["One", "Two", "Three"].map((t) => ({ id: t.toLowerCase(), title: t, render: () => <p>{t} body</p> }));

function mock() {
  let ticked: string[] = [];
  const calls: { method: string; url: string; body?: { library_ids?: string[] } }[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    const method = init?.method ?? "GET";
    const body = init?.body ? JSON.parse(String(init.body)) : undefined;
    calls.push({ method, url, body });
    if (url.endsWith("/context") && method === "PUT") ticked = body.library_ids;
    if (url.endsWith("/context")) return json(200, { library_ids: ticked, items: ticked.map((i) => item(i, "policy.md")) });
    if (url.startsWith("/api/v1/library/folders")) return json(200, { folders: [{ folder: "Policies and rules", icon: "policy", count: 1, items: [item("lib_a", "policy.md")] }], sorting: false, all: ["Policies and rules", "Other"] });
    if (url.startsWith("/api/v1/library")) return json(200, [item("lib_a", "policy.md")]);
    return json(404, {});
  }));
  return calls;
}
const view = (iid = "i1") => render(
  <ThemeProvider><Workbench layoutKey="test" documents={DOCS} agent="North" iid={iid} chatLog={<p>hello</p>} composer={<p>box</p>} /></ThemeProvider>,
);

beforeEach(() => localStorage.clear());
afterEach(() => vi.unstubAllGlobals());

test("enlarge, Esc, close, reopen from the menu, pin, and the layout is remembered", () => {
  mock();
  const { unmount } = view();
  expect(screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent)).toEqual(["Documents", "One", "Two", "Three"]);

  fireEvent.click(screen.getByRole("button", { name: "Enlarge Two" }));
  expect(screen.queryByText("One body")).toBeNull();
  expect(screen.getByRole("button", { name: "Open One" })).toBeInTheDocument();  // the thin tab
  fireEvent.keyDown(window, { key: "Escape" });
  expect(screen.getByText("One body")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Close Three" }));
  expect(screen.queryByText("Three body")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: /Documents menu/ }));
  fireEvent.click(screen.getByRole("checkbox", { name: "Three" }));
  expect(screen.getByText("Three body")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Pin Two" }));
  expect(screen.getAllByRole("heading", { level: 2 }).slice(1).map((h) => h.textContent)).toEqual(["Two", "One", "Three"]);

  fireEvent.click(screen.getByRole("button", { name: "Close One" }));
  unmount();
  view();
  expect(screen.queryByText("One body")).toBeNull();
  expect(screen.getByRole("button", { name: "Unpin Two" })).toBeInTheDocument();
});

test("the layout still works when storage is blocked", () => {
  mock();
  vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => { throw new Error("blocked"); });
  vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("blocked"); });
  view();
  fireEvent.click(screen.getByRole("button", { name: "Close One" }));
  expect(screen.queryByText("One body")).toBeNull();
  vi.restoreAllMocks();
});

const FOLDERS = [
  { folder: "Policies and rules", icon: "policy", count: 1, items: [item("lib_a", "policy.md")] },
  { folder: "Statements", icon: "statement", count: 1, items: [item("lib_b", "demo statements.csv")] },
];
function mockLib() {
  let ticked: string[] = [];
  const calls: { method: string; url: string; body?: { library_ids?: string[] } }[] = [];
  const names: Record<string, string> = { lib_a: "policy.md", lib_b: "demo statements.csv" };
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    const method = init?.method ?? "GET";
    const body = init?.body ? JSON.parse(String(init.body)) : undefined;
    calls.push({ method, url, body });
    if (url.endsWith("/context") && method === "PUT") ticked = body.library_ids;
    if (url.endsWith("/context")) return json(200, { library_ids: ticked, items: ticked.map((i) => item(i, names[i] ?? i)) });
    if (url.startsWith("/api/v1/library/folders")) {
      const q = decodeURIComponent(url.split("?q=")[1] ?? "").toLowerCase();
      const folders = FOLDERS.map((f) => ({ ...f, items: f.items.filter((i) => i.name.toLowerCase().includes(q)) })).map((f) => ({ ...f, count: f.items.length })).filter((f) => f.count);
      return json(200, { folders, sorting: false, all: ["Policies and rules", "Statements", "Other"] });
    }
    return json(404, {});
  }));
  return calls;
}
const openDocs = async () => {
  fireEvent.click(screen.getByRole("button", { name: "Add context for a more relevant conversation" }));
  expect(screen.getByRole("button", { name: "Upload from this computer" })).toBeInTheDocument();
  const opener = screen.getByRole("button", { name: "Saved documents" });
  opener.focus();
  fireEvent.click(opener);
  return { opener, dialog: await screen.findByRole("dialog", { name: "Saved documents" }) };
};

test("UX2: Saved documents opens its own window with folders, counts and every file listed; focus moves in and the page does not scroll", async () => {
  mockLib();
  view();
  expect(await screen.findByText(/North is reading only what you add/)).toBeInTheDocument();
  const { dialog } = await openDocs();
  expect(dialog).toHaveAttribute("aria-modal", "true");
  expect(document.body.style.overflow).toBe("hidden");
  expect(screen.getByRole("searchbox", { name: "Search the library" }).closest("[role=dialog]")).toBe(dialog);
  await waitFor(() => expect(screen.getByRole("searchbox", { name: "Search the library" })).toHaveFocus());
  expect(await screen.findByRole("button", { name: "Policies and rules, 1 file" })).toBeInTheDocument();
  expect(screen.getByRole("checkbox", { name: "Use policy.md in this conversation" })).toBeInTheDocument();  // all folders at first
  expect(screen.getByRole("checkbox", { name: "Use demo statements.csv in this conversation" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Open policy.md in a new tab" })).toHaveAttribute("href", "/centre/build/i1/source?file=documents%2Fpolicy.md");
  expect(screen.getByRole("link", { name: "Open the library in a new tab" })).toHaveAttribute("href", "/centre/library?iid=i1");  // UX3
  fireEvent.click(screen.getByRole("button", { name: "Statements, 1 file" }));
  expect(screen.queryByRole("checkbox", { name: "Use policy.md in this conversation" })).toBeNull();
  expect(screen.getByRole("checkbox", { name: "Use demo statements.csv in this conversation" })).toBeInTheDocument();
});

test("UX2: the search finds file names across all folders", async () => {
  mockLib();
  view();
  await openDocs();
  fireEvent.click(await screen.findByRole("button", { name: "Policies and rules, 1 file" }));
  fireEvent.change(screen.getByRole("searchbox", { name: "Search the library" }), { target: { value: "statements" } });
  expect(await screen.findByRole("checkbox", { name: "Use demo statements.csv in this conversation" })).toBeInTheDocument();
  await waitFor(() => expect(screen.queryByRole("checkbox", { name: "Use policy.md in this conversation" })).toBeNull());
});

test("UX2: choose, then Use N files: the chips show what North reads, an untick removes them, nothing is ticked at first", async () => {
  const calls = mockLib();
  view();
  expect(await screen.findByText(/North is reading only what you add/)).toBeInTheDocument();
  const { opener } = await openDocs();
  fireEvent.click(await screen.findByRole("checkbox", { name: "Use demo statements.csv in this conversation" }));
  expect(calls.some((c) => c.method === "PUT")).toBe(false);  // held in the window until Use
  fireEvent.click(screen.getByRole("button", { name: "Use 1 file in the conversation" }));
  expect(await screen.findByRole("button", { name: "Untick demo statements.csv" })).toBeInTheDocument();
  expect(screen.getByText("North is reading 1 file:")).toBeInTheDocument();
  expect(calls.find((c) => c.method === "PUT")?.body).toEqual({ library_ids: ["lib_b"] });
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  expect(opener).toHaveFocus();
  expect(document.body.style.overflow).toBe("");
  fireEvent.click(screen.getByRole("button", { name: "Untick demo statements.csv" }));
  await waitFor(() => expect(screen.queryByRole("button", { name: "Untick demo statements.csv" })).toBeNull());
});

test("UX2: Escape and Cancel close the window without changing the conversation, and focus returns to Saved documents", async () => {
  const calls = mockLib();
  view();
  const first = await openDocs();
  fireEvent.click(await screen.findByRole("checkbox", { name: "Use policy.md in this conversation" }));
  fireEvent.keyDown(first.dialog, { key: "Escape" });
  expect(screen.queryByRole("dialog")).toBeNull();
  expect(first.opener).toHaveFocus();
  fireEvent.click(first.opener);
  await screen.findByRole("dialog", { name: "Saved documents" });
  expect(screen.getByRole("checkbox", { name: "Use policy.md in this conversation" })).not.toBeChecked();
  fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
  expect(screen.queryByRole("dialog")).toBeNull();
  expect(calls.some((c) => c.method === "PUT")).toBe(false);
});

test("UX2: Tab stays inside the window", async () => {
  mockLib();
  view();
  const { dialog } = await openDocs();
  await screen.findByRole("checkbox", { name: "Use policy.md in this conversation" });
  const use = screen.getByRole("button", { name: "Use 0 files in the conversation" });
  use.focus();
  fireEvent.keyDown(dialog, { key: "Tab" });
  expect(screen.getByRole("searchbox", { name: "Search the library" })).toHaveFocus();
  fireEvent.keyDown(dialog, { key: "Tab", shiftKey: true });
  expect(use).toHaveFocus();
});

test("the layout is remembered per person: another person's key is not read, and Pin, Enlarge and Close are labelled icon buttons", () => {
  mock();
  localStorage.setItem("sh.workbench.someone-else.test", JSON.stringify({ closed: ["one"], enlarged: null, pinned: null }));
  view();
  expect(screen.getByText("One body")).toBeInTheDocument();  // not the other person's layout
  for (const name of ["Pin One", "Enlarge One", "Close One"]) {
    const b = screen.getByRole("button", { name });
    expect(b).toHaveClass("wb-icon");
    expect(b).not.toHaveTextContent(/\w/);  // the drawing is decorative; the name is for screen readers
  }
  fireEvent.click(screen.getByRole("button", { name: "Close One" }));
  expect(Object.keys(localStorage).filter((k) => k.startsWith("sh.workbench.")).sort()).toEqual(["sh.workbench.guest.test", "sh.workbench.someone-else.test"]);
});

test("two columns: chat left, documents right; collapse, divider keys and focus swap the widths", () => {
  mock();
  view();
  const docs = screen.getByRole("region", { name: "Documents" });
  const chat = screen.getByRole("region", { name: "Conversation with North" }).parentElement as HTMLElement;
  expect(chat.compareDocumentPosition(docs) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(chat.style.flexGrow).toBe("60");
  expect(docs.style.flexGrow).toBe("40");

  fireEvent.click(screen.getByRole("button", { name: "Collapse One" }));
  expect(screen.queryByText("One body")).toBeNull();
  expect(screen.getByRole("heading", { level: 2, name: "One" })).toBeInTheDocument();  // the title bar stays
  fireEvent.click(screen.getByRole("button", { name: "Expand One" }));
  expect(screen.getByText("One body")).toBeInTheDocument();

  const bar = screen.getByRole("separator");
  fireEvent.keyDown(bar, { key: "ArrowLeft" });
  fireEvent.keyDown(bar, { key: "ArrowLeft" });
  fireEvent.keyDown(bar, { key: "ArrowLeft" });
  expect(chat.style.flexGrow).toBe("45");
  for (let i = 0; i < 5; i++) fireEvent.keyDown(bar, { key: "ArrowLeft" });
  expect(chat.style.flexGrow).toBe("40");  // the chat never goes under 40%
  expect(localStorage.getItem("sh.workbench.guest.test.split")).toBe("40");

  fireEvent.keyDown(bar, { key: "ArrowRight" });
  fireEvent.click(screen.getByRole("button", { name: "Focus on document" }));
  expect(chat.style.flexGrow).toBe("40");
  expect(docs.style.flexGrow).toBe("60");
  fireEvent.click(screen.getByRole("button", { name: "Back to chat" }));
  expect(chat.style.flexGrow).toBe("45");
});

// L2: proposed changes show in the bar and in their document; Accept and Not this (with an optional reason) call back.
it("shows pending proposals with Accept and Not this, and marks the changed lines", () => {
  mock();
  const onAccept = vi.fn(), onReject = vi.fn();
  const proposals = [{ id: "pr_1", document: "sow", summary: "North changed 3 things in the intent of work", by: "north", changes: [
    { op: "add" as const, path: "kpis/Net worth", before: "", after: "Net worth monthly" },
    { op: "change" as const, path: "goal/why", before: "Old words", after: "New words" },
    { op: "remove" as const, path: "sources/Old file", before: "Old file", after: "" }] }];
  const docs = [{ id: "one", title: "One", proposes: ["sow"], render: () => <p>Old words here</p> }];
  render(<ThemeProvider><Workbench layoutKey="l2" documents={docs} agent="North" iid="i1" chatLog={<p>hello</p>} composer={<p>box</p>}
    proposals={proposals} onAccept={onAccept} onReject={onReject} /></ThemeProvider>);
  expect(screen.getByText("North changed 3 things in the intent of work")).toBeTruthy();
  expect(document.querySelector(".wb-line--add")?.textContent).toContain("Net worth monthly");
  expect(document.querySelector(".wb-line--remove s")).toBeTruthy();
  expect(screen.getByText("Old words here").className).toContain("wb-hl-changed");
  fireEvent.click(screen.getByRole("button", { name: "Accept" }));
  expect(onAccept).toHaveBeenCalledWith("pr_1");
  fireEvent.click(screen.getByRole("button", { name: "Not this" }));
  fireEvent.change(screen.getByLabelText(/Why not/), { target: { value: "Wrong entity" } });
  fireEvent.click(screen.getByRole("button", { name: "Turn it down" }));
  expect(onReject).toHaveBeenCalledWith("pr_1", "Wrong entity");
});
