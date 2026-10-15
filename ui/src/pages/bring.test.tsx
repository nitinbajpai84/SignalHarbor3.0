import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import App from "../App";
import { setSessionExpiredHandler } from "../api/client";

// Bring what you have: nine input tiles, readiness progress, and requests from Nira.
// Tests cover screen states and key interactions.

interface Group { id: number; key: string; title: string; required: boolean; state: string; reason: string; files: string[] }
interface Ask { group: number; title: string; holder: { name: string | null; role: string | null; email: string | null } | null }
interface Readiness { groups: Group[]; percent: number; read: number; sentence: string; asks: Ask[] }

const states = ["read", "partly", "missing"] as const;
const groups: Group[] = Array.from({ length: 9 }, (_, i) => ({
  id: i + 1, key: `g${i + 1}`, title: `Input ${i + 1}`, required: i % 2 === 0,
  state: states[Math.floor(Math.random() * 3)] ?? "missing",
  reason: "Test reason.", files: []
}));

const readiness = (over: object = {}): Readiness => ({
  groups, percent: 85, read: 6, sentence: "Lens has read 6 of 9 inputs.",
  asks: [
    { group: 1, title: "Treasury plan", holder: { name: "Ethan", role: "treasurer", email: "e@co.test" } },
  ],
  ...over,
});

interface World { readinessStatus?: number; readinessData?: Readiness; hold?: boolean; roles?: string[] }
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
      if (url === "/api/auth/me") return json(200, { display_name: "Organiser", company_id: "co-a", roles: w.roles ?? ["company_admin"] });
      if (url === "/api/company") return json(200, { company_id: "co-a", name: "Lakeside Test Co", industry: "family_office" });
      if (url === "/api/profile/readiness") {
        if (w.hold) return new Promise<Response>(() => undefined);
        if (w.readinessStatus) return json(w.readinessStatus, { error: "x", message: "x" });
        return json(200, w.readinessData ?? readiness());
      }
      if (url.includes("/inputs/") && url.includes("/upload") && method === "POST") return json(200, { results: [{ name: "test.csv", result: "read", reason: "" }] });
      if (url.includes("/inputs/") && url.includes("/ask") && method === "POST") return json(200, { email: { subject: "Please send", body: "The treasury...", link: "/company/bring?ask=1" } });
      if (url === "/api/profile/read" && method === "POST") return json(200, readiness());
      return json(404, {});
    }),
  );
}

function open() {
  return render(
    <MemoryRouter initialEntries={["/company/bring"]}>
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

describe("bring what you have", () => {
  test("loading state", async () => {
    mock({ hold: true });
    open();
    expect(await screen.findByRole("heading", { name: "Bring what you have" })).toBeInTheDocument();
    expect(await screen.findByRole("status")).toHaveTextContent("Loading");
  });

  test("empty state", async () => {
    mock({ readinessData: readiness({ groups: [] }) });
    open();
    expect(await screen.findByText(/Nothing has been brought yet/)).toBeInTheDocument();
  });

  test("populated state shows readiness and tiles", async () => {
    mock({});
    open();
    expect(await screen.findByText(/How much Lens can draft/)).toBeInTheDocument();
    expect(screen.getByText("85%")).toBeInTheDocument();
    expect(screen.getByText("1. Input 1")).toBeInTheDocument();
  });

  test("read again button is present", async () => {
    mock({});
    open();
    expect(await screen.findByRole("button", { name: "Read again" })).toBeInTheDocument();
  });

  test("sidebar shows where files live", async () => {
    mock({});
    open();
    expect(await screen.findByText("Where this lives")).toBeInTheDocument();
    expect(screen.getByText("This company's space, on this machine")).toBeInTheDocument();
  });

  test("Nira section lists missing items", async () => {
    mock({});
    open();
    expect(await screen.findByText("Nira · What is missing, from whom")).toBeInTheDocument();
    expect(screen.getByText("Treasury plan")).toBeInTheDocument();
  });

  test("write request button is present", async () => {
    mock({});
    open();
    await screen.findByText("Treasury plan");
    expect(screen.getByRole("button", { name: /Write the request/ })).toBeInTheDocument();
  });
});
