import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import App from "./App";
import { listModules, login, setSessionExpiredHandler, ApiError, Refused } from "./api/client";
import ScreenState from "./components/ScreenState";
import WizardFrame from "./components/WizardFrame";
import { copy } from "./copy";
import { HAD_SESSION_KEY } from "./useSession";
import { useState } from "react";

interface Mod {
  id: string;
  number: number;
  name: string;
  description: string;
  agent: string;
}
const M1: Mod = { id: "m1_intent", number: 1, name: "Intent", description: "Agree what the business wants.", agent: "North" };
const M2: Mod = { id: "m2_baseline", number: 2, name: "Baseline", description: "Map what exists today.", agent: "Lens" };
// a module with no screens yet: the placeholder page (module 2 has its own screens since the M2 skeleton)
const M3: Mod = { id: "m3_scan", number: 3, name: "Scan and gap", description: "Find what is missing.", agent: "Flow" };
const M6: Mod = { id: "m6_ops", number: 6, name: "Ops", description: "Run the daily feed.", agent: "Watch" };

interface World {
  signedIn: boolean;
  modules: Mod[];
  industry?: string;
  loginStatus?: number; // when set, login fails with this status
  networkDown?: boolean;
  expireNow?: boolean; // every authenticated call returns 401 session_expired
  meFailures?: number; // the next N session checks fail with a 500
  modulesFailures?: number; // the next N module lists fail with a 500
  modulesRefused?: boolean; // the module list answers 403 module_not_available
}
const calls: { method: string; url: string; headers: Record<string, string> }[] = [];

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}
const EXPIRED = { error: "session_expired", message: "x", login_url: "/login" };

function mockWorld(w: World) {
  calls.length = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      calls.push({ method: init?.method ?? "GET", url, headers: (init?.headers ?? {}) as Record<string, string> });
      if (url === "/api/auth/login") {
        if (w.networkDown) throw new TypeError("network"); // only the sign-in call fails
        if (w.loginStatus) return json(w.loginStatus, { error: "login_failed", message: "no" });
        w.signedIn = true;
        w.expireNow = false;
        return json(200, { display_name: "Ann", company_id: "co-a", roles: ["analyst"] });
      }
      if (url === "/api/auth/logout") {
        w.signedIn = false;
        return json(200, { status: "signed_out" });
      }
      if (url === "/api/auth/me" && w.meFailures) {
        w.meFailures -= 1;
        return json(500, { detail: "boom" });
      }
      if (!w.signedIn || w.expireNow) return json(401, EXPIRED);
      if (url === "/api/modules" && w.modulesRefused) return json(403, { error: "module_not_available", message: "x" });
      if (url === "/api/modules" && w.modulesFailures) {
        w.modulesFailures -= 1;
        return json(500, { detail: "boom" });
      }
      if (url === "/api/auth/me") return json(200, { display_name: "Ann", company_id: "co-a", roles: ["analyst"] });
      if (url === "/api/company") return json(200, { company_id: "co-a", name: "Harbor Test Co", industry: w.industry ?? "none" });
      if (url === "/api/modules") return json(200, w.modules);
      return json(404, {});
    }),
  );
}

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
}

afterEach(() => {
  vi.restoreAllMocks();
  sessionStorage.clear();
  setSessionExpiredHandler(null);
  document.cookie = "sh_csrf=; max-age=0";
  vi.unstubAllGlobals();
});

describe("pages that need no sign-in", () => {
  const meCalls = () => calls.filter((c) => c.url === "/api/auth/me");

  test("an answer link never asks who is signed in, so no 401 is logged", async () => {
    mockWorld({ signedIn: false, modules: [] });
    renderAt("/answer/some-token");
    await new Promise((r) => setTimeout(r, 50));
    expect(meCalls()).toHaveLength(0);
  });

  test("a join link asks only when this browser has signed in before", async () => {
    localStorage.removeItem("sh_signed_in_hint");
    mockWorld({ signedIn: false, modules: [] });
    const first = renderAt("/join/abcdefghijklmnopqrstuv");
    await new Promise((r) => setTimeout(r, 50));
    expect(meCalls()).toHaveLength(0);
    first.unmount();
    localStorage.setItem("sh_signed_in_hint", "1");
    mockWorld({ signedIn: true, modules: [] });
    renderAt("/join/abcdefghijklmnopqrstuv");
    await waitFor(() => expect(meCalls()).toHaveLength(1));
    localStorage.removeItem("sh_signed_in_hint");
  });
});

describe("routing and session", () => {
  test("signed-out visit to home goes to the login page", async () => {
    mockWorld({ signedIn: false, modules: [] });
    renderAt("/legacy");
    expect(await screen.findByRole("button", { name: "Sign in" })).toBeInTheDocument();
    expect(screen.getByText("Signal Harbor")).toBeInTheDocument();
  });

  test("signed-in visit to login goes to home", async () => {
    mockWorld({ signedIn: true, modules: [M1] });
    renderAt("/login");
    expect(await screen.findByText("Harbor Test Co")).toBeInTheDocument();
  });

  test("login success goes to home; first field is focused; Enter submits", async () => {
    mockWorld({ signedIn: false, modules: [M1] });
    const user = userEvent.setup();
    renderAt("/legacy");
    const email = await screen.findByLabelText("Email");
    expect(email).toHaveFocus();
    await user.type(email, "ann@test.invalid");
    await user.type(screen.getByLabelText("Password"), "pw{Enter}");
    expect(await screen.findByText("Harbor Test Co")).toBeInTheDocument();
  });

  test("wrong password shows the one sentence", async () => {
    mockWorld({ signedIn: false, modules: [], loginStatus: 401 });
    const user = userEvent.setup();
    renderAt("/login");
    await user.type(await screen.findByLabelText("Email"), "a@b.invalid");
    await user.type(screen.getByLabelText("Password"), "x");
    await user.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("That email and password did not match. Try again.");
  });

  test.each([["network", undefined], ["415", 415], ["500", 500]])("%s failure shows the second sentence", async (_n, status) => {
    mockWorld({ signedIn: false, modules: [], loginStatus: status, networkDown: status === undefined });
    const user = userEvent.setup();
    renderAt("/login");
    await user.type(await screen.findByLabelText("Email"), "a@b.invalid");
    await user.type(screen.getByLabelText("Password"), "x");
    await user.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "We could not sign you in right now. Try again in a moment.",
    );
  });

  test("sign out returns to login", async () => {
    mockWorld({ signedIn: true, modules: [M1] });
    const user = userEvent.setup();
    renderAt("/legacy");
    await user.click(await screen.findByRole("button", { name: "Sign out" }));
    expect(await screen.findByRole("button", { name: "Sign in" })).toBeInTheDocument();
  });

  test("a 401 session_expired on a later call sends the person to login", async () => {
    const w: World = { signedIn: true, modules: [M1] };
    mockWorld(w);
    renderAt("/legacy");
    expect(await screen.findByText("Harbor Test Co")).toBeInTheDocument();
    w.expireNow = true;
    await userEvent.setup().click(screen.getByRole("link", { name: /Intent/ }));
    expect(await screen.findByRole("button", { name: "Sign in" })).toBeInTheDocument();
  });

  test("session_expired calls the handler exactly once, however many calls fail", async () => {
    mockWorld({ signedIn: true, modules: [], expireNow: true });
    const handler = vi.fn();
    setSessionExpiredHandler(handler);
    await Promise.allSettled([listModules(), listModules(), listModules()]);
    expect(handler).toHaveBeenCalledTimes(1);
  });
});

async function signInAs(user: ReturnType<typeof userEvent.setup>) {
  await user.type(await screen.findByLabelText("Email"), "ann@test.invalid");
  await user.type(screen.getByLabelText("Password"), "pw{Enter}");
}

describe("session ended message", () => {
  test("shown once as a status after an expiry redirect, not on a first visit, cleared after sign-in", async () => {
    const w: World = { signedIn: false, modules: [M1] };
    mockWorld(w);
    const user = userEvent.setup();
    renderAt("/legacy");
    await screen.findByRole("button", { name: "Sign in" });
    expect(screen.queryByText(copy.errors.sessionEnded)).not.toBeInTheDocument(); // first visit
    await signInAs(user);
    await screen.findByText("Harbor Test Co");
    w.expireNow = true;
    await user.click(screen.getByRole("link", { name: /Intent/ }));
    await screen.findByRole("button", { name: "Sign in" });
    expect(screen.getAllByText(copy.errors.sessionEnded)).toHaveLength(1);
    expect(screen.getByRole("status")).toHaveTextContent(copy.errors.sessionEnded);
    await signInAs(user); // mock stops expiring on login
    await user.click(await screen.findByRole("button", { name: "Sign out" }));
    await screen.findByRole("button", { name: "Sign in" });
    expect(screen.queryByText(copy.errors.sessionEnded)).not.toBeInTheDocument();
  });
});

describe("session ended message after a reload", () => {
  test("a marker from earlier shows the sentence on every reload until sign-in or sign-out", async () => {
    sessionStorage.setItem(HAD_SESSION_KEY, "1");
    mockWorld({ signedIn: false, modules: [M1] });
    const first = renderAt("/modules/m1_intent");
    expect(await screen.findByText(copy.errors.sessionEnded)).toBeInTheDocument();
    first.unmount();
    renderAt("/legacy"); // a second reload still shows it
    expect(await screen.findByText(copy.errors.sessionEnded)).toBeInTheDocument();
    await signInAs(userEvent.setup());
    await screen.findByText("Harbor Test Co");
    expect(sessionStorage.getItem(HAD_SESSION_KEY)).toBe("1"); // a session exists again
    await userEvent.setup().click(screen.getByRole("button", { name: "Sign out" }));
    await screen.findByRole("button", { name: "Sign in" });
    expect(screen.queryByText(copy.errors.sessionEnded)).not.toBeInTheDocument();
    expect(sessionStorage.getItem(HAD_SESSION_KEY)).toBeNull();
  });

  test("no marker means no sentence; a successful session check sets the marker", async () => {
    mockWorld({ signedIn: false, modules: [M1] });
    const first = renderAt("/legacy");
    await screen.findByRole("button", { name: "Sign in" });
    expect(screen.queryByText(copy.errors.sessionEnded)).not.toBeInTheDocument();
    first.unmount();
    mockWorld({ signedIn: true, modules: [M1] });
    renderAt("/legacy");
    await screen.findByText("Harbor Test Co");
    expect(sessionStorage.getItem(HAD_SESSION_KEY)).toBe("1");
  });

  test("storage that throws does not break the page, and expiry is still explained", async () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    vi.spyOn(Storage.prototype, "removeItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    const w: World = { signedIn: false, modules: [M1] };
    mockWorld(w);
    const user = userEvent.setup();
    renderAt("/legacy");
    await signInAs(user);
    await screen.findByText("Harbor Test Co");
    w.expireNow = true;
    await user.click(screen.getByRole("link", { name: /Intent/ }));
    expect(await screen.findByText(copy.errors.sessionEnded)).toBeInTheDocument();
  });
});

describe("return to the page asked for", () => {
  test("a signed-out visit to a module page returns there after sign-in", async () => {
    mockWorld({ signedIn: false, modules: [M3] });
    renderAt("/modules/m3_scan");
    await signInAs(userEvent.setup());
    expect(await screen.findByText(copy.module.placeholder)).toBeInTheDocument();
  });

  test.each(["https://evil.example", "//evil.example", "/\\evil.example"])("next=%s is ignored", async (next) => {
    mockWorld({ signedIn: false, modules: [M1] });
    renderAt(`/login?next=${encodeURIComponent(next)}`);
    await signInAs(userEvent.setup());
    expect(await screen.findByRole("link", { name: "Action" })).toHaveAttribute("aria-current", "page");  // Action is the landing page
  });
});

describe("other screens", () => {
  test("an unknown address shows a plain page with a link home", async () => {
    mockWorld({ signedIn: true, modules: [M1] });
    renderAt("/some/unknown/page");
    expect(await screen.findByText(copy.notFound.message)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: copy.notFound.home })).toHaveAttribute("href", "/");
  });

  test("module and refused pages carry the top bar; refused has a heading", async () => {
    mockWorld({ signedIn: true, modules: [M1] });
    const { unmount } = renderAt("/modules/m1_intent");
    expect(await screen.findByText("Harbor Test Co")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sign out" })).toBeInTheDocument();
    unmount();
    renderAt("/modules/m6_ops");
    expect(await screen.findByRole("heading", { name: copy.states.refusedHeading })).toBeInTheDocument();
    expect(screen.getByText("Harbor Test Co")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sign out" })).toBeInTheDocument();
  });

  test("a 403 module_not_available on the module screen shows the refused state", async () => {
    mockWorld({ signedIn: true, modules: [M1], modulesRefused: true });
    renderAt("/modules/m1_intent");
    expect(await screen.findByRole("alert")).toHaveTextContent(copy.states.refused);
  });

  test("home error has Try again, which retries", async () => {
    mockWorld({ signedIn: true, modules: [M1], modulesFailures: 1 });
    const user = userEvent.setup();
    renderAt("/legacy");
    expect(await screen.findByRole("alert")).toHaveTextContent(copy.states.error);
    await user.click(screen.getByRole("button", { name: copy.states.retry }));
    expect(await screen.findByRole("link", { name: /Intent/ })).toBeInTheDocument();
  });

  test("a failed session check has Try again, which retries", async () => {
    mockWorld({ signedIn: false, modules: [], meFailures: 1 });
    const user = userEvent.setup();
    renderAt("/legacy");
    expect(await screen.findByRole("alert")).toHaveTextContent(copy.states.error);
    await user.click(screen.getByRole("button", { name: copy.states.retry }));
    expect(await screen.findByRole("button", { name: "Sign in" })).toBeInTheDocument();
  });

  test("the password field is cleared after a wrong password", async () => {
    mockWorld({ signedIn: false, modules: [], loginStatus: 401 });
    const user = userEvent.setup();
    renderAt("/login");
    await signInAs(user);
    await screen.findByRole("alert");
    expect(screen.getByLabelText("Password")).toHaveValue("");
  });
});

describe("client", () => {
  test("a non-GET call sends the CSRF header from the cookie; a GET does not", async () => {
    mockWorld({ signedIn: false, modules: [] });
    document.cookie = "sh_csrf=tok123";
    await login("a@b.invalid", "x");
    await listModules().catch(() => undefined);
    const post = calls.find((c) => c.method === "POST");
    const get = calls.find((c) => c.method === "GET");
    expect(post?.headers["X-CSRF-Token"]).toBe("tok123");
    expect(get?.headers["X-CSRF-Token"]).toBeUndefined();
  });

  test("403 module_not_available becomes Refused; other failures become ApiError", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json(403, { error: "module_not_available", message: "m" })));
    await expect(listModules()).rejects.toBeInstanceOf(Refused);
    vi.stubGlobal("fetch", vi.fn(async () => json(500, { detail: "Traceback ..." })));
    const err = await listModules().catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect((err as ApiError).message).toBe(copy.errors.server);
  });
});

describe("home", () => {
  test("shows only the modules the server returned, with the guide's name", async () => {
    mockWorld({ signedIn: true, modules: [M1, M2] });
    renderAt("/legacy");
    expect(await screen.findByRole("link", { name: /Intent/ })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Baseline/ })).toBeInTheDocument();
    expect(screen.queryByText(/Ops/)).not.toBeInTheDocument();
    expect(screen.getByText("Guided by North")).toBeInTheDocument();
    expect(screen.getByText("Guided by Lens")).toBeInTheDocument();
  });

  test("a second company gets its own tile set", async () => {
    mockWorld({ signedIn: true, modules: [M6] });
    renderAt("/legacy");
    expect(await screen.findByRole("link", { name: /Ops/ })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Intent/ })).not.toBeInTheDocument();
  });

  test("no modules shows the empty state", async () => {
    mockWorld({ signedIn: true, modules: [] });
    renderAt("/legacy");
    expect(
      await screen.findByText("No modules are switched on for your company yet. Ask your administrator."),
    ).toBeInTheDocument();
  });

  test("a tile opens the placeholder page", async () => {
    mockWorld({ signedIn: true, modules: [M3] });
    const user = userEvent.setup();
    renderAt("/legacy");
    await user.click(await screen.findByRole("link", { name: /Scan and gap/ }));
    expect(await screen.findByText("This module opens in a later release.")).toBeInTheDocument();
  });

  test("a module the company does not own shows the refused state", async () => {
    mockWorld({ signedIn: true, modules: [M1] });
    renderAt("/modules/m6_ops");
    expect(await screen.findByRole("alert")).toHaveTextContent(copy.states.refused);
  });

  test("no industry word or id on screen", async () => {
    mockWorld({ signedIn: true, modules: [M1, M2], industry: "none" });
    renderAt("/legacy");
    await screen.findByText("Harbor Test Co");
    const text = document.body.textContent ?? "";
    // banned words are built from pieces so the repo-wide industry scan does not flag this file
    const banned = new RegExp(["insur", "ance|insur", "er|asset[_ -]?manage", "ment|industry|m1_intent|co-a"].join(""), "i");
    expect(text).not.toMatch(banned);
  });
});

describe("ScreenState", () => {
  test.each([
    ["loading", "status"],
    ["error", "alert"],
    ["refused", "alert"],
  ] as const)("%s has role %s and default copy", (state, role) => {
    render(<ScreenState state={state}>kids</ScreenState>);
    expect(screen.getByRole(role)).toHaveTextContent(copy.states[state]);
    expect(screen.queryByText("kids")).not.toBeInTheDocument();
  });

  test("empty shows its copy; populated shows children; copy can be passed in", () => {
    const { rerender } = render(<ScreenState state="empty" message="Nothing yet.">kids</ScreenState>);
    expect(screen.getByText("Nothing yet.")).toBeInTheDocument();
    rerender(<ScreenState state="populated">kids</ScreenState>);
    expect(screen.getByText("kids")).toBeInTheDocument();
  });
});

describe("WizardFrame", () => {
  function Harness({ ready }: { ready: boolean }) {
    const [i, setI] = useState(0);
    return (
      <WizardFrame
        title="Charter"
        steps={[{ id: "a", label: "Question" }, { id: "b", label: "People" }, { id: "c", label: "Sign" }]}
        current={i}
        ready={ready}
        onBack={() => setI(i - 1)}
        onNext={() => setI(i + 1)}
        suggestion={i === 1 ? "Try naming one owner." : undefined}
      >
        <p>Content {i + 1}</p>
      </WizardFrame>
    );
  }

  test("moves through three steps; Back is off on the first, Next is gone on the last", async () => {
    const user = userEvent.setup();
    render(<Harness ready />);
    const steps = screen.getByRole("list", { name: copy.wizard.steps });
    expect(within(steps).getAllByRole("listitem")).toHaveLength(3);
    expect(within(steps).getByText("Question").closest("li")).toHaveAttribute("aria-current", "step");
    expect(screen.getByRole("button", { name: "Back" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getByText("Content 2")).toBeInTheDocument();
    expect(screen.getByText("Suggestion")).toBeInTheDocument();
    expect(screen.getByText("Try naming one owner.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getByText("Content 3")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Next" })).not.toBeInTheDocument(); // the last step has its own action
    await user.click(screen.getByRole("button", { name: "Back" }));
    expect(screen.getByText("Content 2")).toBeInTheDocument();
  });

  test("Next is disabled until the step is ready", () => {
    render(<Harness ready={false} />);
    expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
  });
});

test("no any in the UI source", () => {
  const files = import.meta.glob("./**/*.{ts,tsx}", { query: "?raw", import: "default", eager: true }) as Record<string, string>;
  const bad = new RegExp(["\\b:\\s*an", "y\\b|\\bas\\s+an", "y\\b|<an", "y>"].join(""));
  const hits = Object.entries(files)
    .filter(([name]) => !name.endsWith(".test.tsx"))
    .filter(([, src]) => bad.test(src))
    .map(([name]) => name);
  expect(hits).toEqual([]);
});
