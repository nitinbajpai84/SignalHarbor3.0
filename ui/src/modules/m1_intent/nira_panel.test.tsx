import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import { m1Companion, m1Nira, type CompanionStage } from "./copy";
import NiraDock from "./NiraDock";

// M1-UI2: Nira docked on every module 1 screen: four sections per stage, the ask box on the existing route, collapsed on a phone.

const SID = "a".repeat(32);
const calls: { method: string; url: string; body: unknown }[] = [];
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

function mock() {
  calls.length = 0;
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    calls.push({ method: init?.method ?? "GET", url, body: init?.body ? JSON.parse(String(init.body)) : undefined });
    if (url.endsWith("/nira")) {
      const kind = (JSON.parse(String(init?.body)) as { kind: string }).kind;
      return json(200, { available: true, name: "Nira", role: "the guide", text: kind === "welcome" ? "Welcome, we are here to agree what the family office tracks." : "Fees are shared as the rules say." });
    }
    return json(404, {});
  }));
}
const dock = (stage: CompanionStage, sessionId = SID) =>
  render(<MemoryRouter><NiraDock sessionId={sessionId} stage={stage} actions={[{ label: "Take me on", to: "/x" }]} /></MemoryRouter>);

const STAGES = Object.keys(m1Companion.stages) as CompanionStage[];

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  localStorage.clear();
  window.innerWidth = 1024;
});

describe("Nira's panel", () => {
  test.each(STAGES)("%s: shows the four sections, this stage's checklist and explanation, and the ask box", async (stage) => {
    mock();
    dock(stage);
    const panel = screen.getByRole("region", { name: m1Nira.name });
    for (const label of Object.values(m1Companion.sections)) expect(within(panel).getByRole("button", { name: label })).toBeInTheDocument();
    const info = m1Companion.stages[stage];
    for (const n of info.needed) expect(within(panel).getByText(n.label)).toBeInTheDocument();
    expect(within(panel).getByText(info.looking)).toBeInTheDocument();
    expect(within(panel).getByText(info.line)).toBeInTheDocument();
    expect(within(panel).getByRole("textbox", { name: m1Nira.question })).toHaveAttribute("placeholder", m1Nira.questionHelp);
    expect(within(panel).getByText(m1Nira.audioNote)).toBeInTheDocument();
    expect(within(panel).getByRole("link", { name: "Take me on" })).toHaveAttribute("href", "/x");
    await waitFor(() => expect(calls.some((c) => (c.body as { kind?: string })?.kind === "welcome")).toBe(true));
  });

  test("her welcome fills the About section; a section opens and closes and is remembered", async () => {
    mock();
    const user = userEvent.setup();
    dock("briefing");
    expect(await screen.findByText(/Welcome, we are here/)).toBeInTheDocument();
    const about = screen.getByRole("button", { name: m1Companion.sections.about });
    expect(about).toHaveAttribute("aria-expanded", "false");
    await user.click(about);
    expect(about).toHaveAttribute("aria-expanded", "true");
    expect(localStorage.getItem("sh:companion-section-about")).toBe("1");
  });

  test("Ask Nira posts the question to the existing route and shows the answer under the person's own words", async () => {
    mock();
    const user = userEvent.setup();
    dock("briefing");
    await user.type(screen.getByRole("textbox", { name: m1Nira.question }), "How are fees shared?{Enter}");
    const log = screen.getByRole("log", { name: m1Nira.conversation });
    await waitFor(() => expect(log).toHaveTextContent("Fees are shared as the rules say."));
    expect(log).toHaveTextContent("How are fees shared?");
    const ask = calls.find((c) => c.method === "POST" && (c.body as { kind?: string })?.kind === "ask");
    expect(ask?.url).toBe(`/api/modules/m1_intent/sessions/${SID}/nira`);
    expect(ask?.body).toEqual({ kind: "ask", question: "How are fees shared?" });
  });

  test("an empty question is not sent", async () => {
    mock();
    const user = userEvent.setup();
    dock("briefing");
    await user.click(screen.getByRole("button", { name: m1Nira.ask }));
    expect(screen.getByRole("alert")).toHaveTextContent(m1Nira.needQuestion);
    expect(calls.some((c) => (c.body as { kind?: string })?.kind === "ask")).toBe(false);
  });

  test("a draft that is not saved yet explains the screen but makes no call", async () => {
    mock();
    const user = userEvent.setup();
    dock("prepare", "");
    await user.type(screen.getByRole("textbox", { name: m1Nira.question }), "Hello{Enter}");
    expect(screen.getByRole("alert")).toHaveTextContent(m1Nira.noSession);
    expect(calls).toEqual([]);
  });

  test("at phone width it is a button; opening it shows the panel and closing returns to the button", async () => {
    mock();
    window.innerWidth = 375;
    const user = userEvent.setup();
    dock("briefing");
    const pill = screen.getByRole("button", { name: /Nira, your companion/ });
    expect(pill).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("region", { name: m1Nira.name })).not.toBeInTheDocument(); // hidden: nothing to read or tab to
    await user.click(pill);
    expect(screen.getByRole("region", { name: m1Nira.name })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Collapse Nira" }));
    expect(screen.queryByRole("region", { name: m1Nira.name })).not.toBeInTheDocument();
  });

  test("on a wide screen it opens docked and keeps the page clear of it", () => {
    mock();
    dock("briefing");
    expect(document.querySelector(".n-companion-dock")).toHaveClass("expanded", "large");
    expect(document.body).toHaveClass("n-companion-open");
    expect(document.documentElement.style.getPropertyValue("--n-companion-reserve")).toBe("360px");
  });
});
