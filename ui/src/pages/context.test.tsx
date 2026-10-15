import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import App from "../App";
import { setSessionExpiredHandler } from "../api/client";

// Company context page: upload documents for agents to read as background.
// Tests cover five screen states, admin permissions, and basic interactions.

const NORTH_DOCS = "/api/agents/north/docs";
const LENS_DOCS = "/api/agents/lens/docs";
const DOC = {
  doc_id: "a".repeat(12), title: "Investment policy", filename: "investment-policy.md", status: "ready",
  visibility: "private", shared_summary: null, uploaded_at: "2026-10-03T10:00:00Z",
};

interface World {
  roles?: string[];
  docs?: (typeof DOC)[];
  hold?: boolean;
  listStatus?: number;
  uploadStatus?: number;
  uploadBody?: unknown;
  pending?: { pending_id: number; kind: string; subject: string; content: string }[];
  maxMb?: number;
  lensDocs?: (typeof DOC)[];
}

const calls: { method: string; url: string; body: unknown; csrf: string | undefined }[] = [];
const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

function mock(w: World) {
  calls.length = 0;
  document.cookie = "sh_csrf=tok123";
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      const method = init?.method ?? "GET";
      calls.push({ method, url, body: init?.body ? JSON.parse(String(init.body)) : undefined,
        csrf: (init?.headers as Record<string, string> | undefined)?.["X-CSRF-Token"] });
      if (url === "/api/auth/me") return json(200, { display_name: "Ann", company_id: "co-a", roles: w.roles ?? ["company_admin"] });
      if (url === "/api/company") return json(200, { company_id: "co-a", name: "Lakeside Test Co", industry: "family_office" });
      if (url === NORTH_DOCS && method === "GET") {
        if (w.hold) return new Promise<Response>(() => undefined);
        if (w.listStatus) return json(w.listStatus, { error: w.listStatus === 403 ? "forbidden" : "x", message: "x" });
        return json(200, { agent: "north", documents: w.docs ?? [], accepted: ["docx", "md", "txt"], max_mb: w.maxMb ?? 15, admin: w.roles?.includes("company_admin") ?? true });
      }
      if (url === LENS_DOCS && method === "GET") {
        if (w.hold) return new Promise<Response>(() => undefined);
        if (w.listStatus) return json(w.listStatus, { error: "x", message: "x" });
        return json(200, { agent: "lens", documents: w.lensDocs ?? [], accepted: ["docx", "md", "txt"], max_mb: w.maxMb ?? 15, admin: w.roles?.includes("company_admin") ?? true });
      }
      if ((url === NORTH_DOCS || url === LENS_DOCS) && method === "POST") return json(w.uploadStatus ?? 200, w.uploadBody ?? DOC);
      if (url === "/api/agents/north/pending-memories") return json(200, { agent: "north", pending: w.pending ?? [] });
      if (url.startsWith(`${NORTH_DOCS}/`) || url.startsWith(`${LENS_DOCS}/`)) return json(200, DOC);
      if (url.includes("/decide")) return json(200, {});
      return json(404, {});
    }),
  );
}

function open() {
  return render(
    <MemoryRouter initialEntries={["/company/context"]}>
      <App />
    </MemoryRouter>,
  );
}

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  sessionStorage.clear();
  setSessionExpiredHandler(null);
});

describe("company context", () => {
  test("loading state", async () => {
    mock({ hold: true });
    open();
    expect(await screen.findByRole("heading", { name: "Company context" })).toBeInTheDocument();
    expect(await screen.findByRole("status")).toHaveTextContent("Loading");
  });

  test("empty state with upload prompt", async () => {
    mock({});
    open();
    expect(await screen.findByText(/No documents yet/)).toBeInTheDocument();
  });

  test("error state with retry", async () => {
    mock({ listStatus: 500 });
    const user = userEvent.setup();
    open();
    expect(await screen.findByRole("alert")).toBeInTheDocument();
    mock({ docs: [DOC] });
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Investment policy")).toBeInTheDocument();
  });

  test("refused state", async () => {
    mock({ listStatus: 403 });
    open();
    expect(await screen.findByRole("alert")).toHaveTextContent("You do not have access");
  });

  test("populated state shows documents", async () => {
    mock({ docs: [DOC] });
    open();
    expect(await screen.findByText("Investment policy")).toBeInTheDocument();
  });

  test("two agents are present", async () => {
    mock({ docs: [DOC], lensDocs: [{ ...DOC, doc_id: "b".repeat(12), title: "Business glossary" }] });
    open();
    expect(await screen.findByText("Investment policy")).toBeInTheDocument();
    expect(screen.getByText("Business glossary")).toBeInTheDocument();
  });

  test("admin sees upload form and pending", async () => {
    mock({ docs: [DOC], pending: [{ pending_id: 1, kind: "memory", subject: "Test", content: "Content" }] });
    open();
    expect(await screen.findByText("Upload a document")).toBeInTheDocument();
    expect(screen.getByText("Memories waiting for review")).toBeInTheDocument();
  });

  test("non-admin does not see upload form", async () => {
    mock({ roles: ["analyst"], docs: [DOC] });
    open();
    expect(await screen.findByText("Investment policy")).toBeInTheDocument();
    expect(screen.getByText(/administrator/)).toBeInTheDocument();
    expect(screen.queryByText("Upload a document")).not.toBeInTheDocument();
  });

  test("pending memories section is visible for admin", async () => {
    mock({ docs: [DOC], pending: [{ pending_id: 1, kind: "memory", subject: "Test", content: "Content" }] });
    open();
    expect(await screen.findByText("Memories waiting for review")).toBeInTheDocument();
  });
});
