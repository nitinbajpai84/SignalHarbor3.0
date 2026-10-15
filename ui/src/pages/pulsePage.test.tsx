import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import PulsePage, { type Line, type Pulse } from "./PulsePage";

// SHAPES section 1 with the role panels the pulse route adds (layout, panels, line minutes). Synthetic people.
const line = (id: string, kind: Line["kind"], title: string, href: string, action = "Open") =>
  ({ id, kind, title, detail: `d ${id}`, href, action, due: null, minutes: 3, source: { record: `sessions/${id}`, at: "2026-10-07T08:00:00Z" } });
const base = (roles: string[], extra: Partial<Pulse>): Pulse => ({
  date: "2026-10-07", person: { name: "Priya Nair", roles }, minutes: 12, strips: [], map: { new_this_week: ["Fees Charged"], owned_changes: 1, owned_new: 1 }, ...extra,
} as Pulse);
const notYet = (label: string) => ({ label, value: null, note: "Not available yet" });

const json = (b: unknown) => new Response(JSON.stringify(b), { status: 200, headers: { "Content-Type": "application/json" } });
const open = (pulse: Pulse) => {
  vi.stubGlobal("fetch", vi.fn(async () => json(pulse)));
  return render(<MemoryRouter><PulsePage /></MemoryRouter>);
};
const labels = (c: HTMLElement) => [...c.querySelectorAll(".ds-strip__label")].map((x) => x.textContent);
afterEach(() => vi.unstubAllGlobals());

describe("Pulse page", () => {
  test("participant: invited, decide, give, watch; each card one click to its screen; map and memory on the side", async () => {
    const { container } = open(base(["participant"], {
      layout: "participant",
      strips: [
        { key: "watch", lines: [line("w1", "brief", "Private credit spreads tightened again", "/centre/consume/market", "Read")] },
        { key: "invited", lines: [line("i1", "invite", "Treasury wall", "/centre/intent/wall/s1", "Open the wall")] },
        { key: "decide", lines: [line("d1", "decision", "Fees Charged", "/centre/intent/baseline/b1", "Confirm")] },
        { key: "give", lines: [line("g1", "request", "Data for Custodian", "/centre/intent/truth/a1", "Send the file")] },
      ],
    }));
    expect(await screen.findByText(/, Priya\./)).toBeInTheDocument();
    expect(screen.getByText(/3 things need you · about 9 minutes/)).toBeInTheDocument();
    expect(labels(container)).toEqual(["Invited", "Decide", "Give", "Watch"]);
    expect(screen.getByRole("link", { name: /Fees Charged/ })).toHaveAttribute("href", "/centre/intent/baseline/b1");
    expect(within(screen.getByRole("link", { name: /Treasury wall/ })).getByText("Open the wall")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Private credit spreads/ })).toHaveAttribute("href", "/centre/consume/market");
    expect(screen.getByText("New this week")).toBeInTheDocument();
    expect(screen.getAllByText("Fees Charged").length).toBeGreaterThan(0);
    expect(screen.getByText("You own one of them.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Read or correct" })).toHaveAttribute("href", "/centre/memory");
  });

  test("organiser: requests to start, walls running, waiting on others, then the quarter's counters", async () => {
    const { container } = open(base(["company_admin"], {
      layout: "organiser",
      strips: [
        { key: "start", lines: [line("s1", "decision", "A note from Mei Tan", "/centre/intent", "Review draft")] },
        { key: "running", lines: [line("r1", "invite", "Treasury: 5 of 8 have not written a card", "/centre/intent/wall/s1"),
          line("r2", "decision", "Performance closed with no charter yet", "/centre/intent/define/s2", "Open Define")] },
        { key: "waiting", lines: [line("q1", "request", "2 baseline measure owner(s) have not answered for more than three days", "/centre/intent/baseline/b1")] },
      ],
      panels: { quarter: [{ label: "Walls run", value: "4", note: null }, { label: "Measures governed", value: "14 of 20", note: null }, notYet("Your time so far")],
        drafts: { sponsor_ask: 1, reminder: 2 } },
    }));
    await screen.findByText(/Requests to start/);
    expect(labels(container)).toEqual(["Requests to start", "Walls running", "Waiting on others", "Your walls so far"]);
    expect(screen.getByRole("link", { name: /closed with no charter/ })).toHaveAttribute("href", "/centre/intent/define/s2");
    expect(screen.getByText("14 of 20")).toBeInTheDocument();
    expect(screen.getByText("Not available yet")).toBeInTheDocument();
    expect(screen.getByText("1 note from a sponsor · 2 reminders")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Review all/ })).toBeNull();
    expect(screen.getByText(/4 things need you · about 12 minutes · Nira, your guide, drafted all of them/)).toBeInTheDocument();
  });

  test("data team: the ops report first with its four counts and the critical line inset, then Sign", async () => {
    const { container } = open(base(["analyst"], {
      layout: "data",
      strips: [
        { key: "ops", lines: [line("c1", "ops", "Critical: TRUST_NAV does not match the reported figure", "/centre/build/prove", "Open in Prove")] },
        { key: "sign", lines: [line("b1", "signature", "The blueprint waits for your signature", "/centre/build/blueprint", "Review blueprint")] },
        { key: "invited", lines: [line("i1", "invite", "Performance wall", "/centre/intent/wall/s2", "Open the wall")] },
      ],
      panels: { ops_report: [{ label: "Loads on time", value: "6 of 7", note: null }, { label: "Late", value: "1", note: null },
        { label: "Checks failed", value: "2", note: null }, notYet("Measures released")] },
    }));
    await screen.findByText("Today's ops report");
    expect(labels(container)).toEqual(["Today's ops report", "Sign", "Invited"]);
    const report = container.querySelector(".ds-strip")!;
    expect(within(report as HTMLElement).getByText("6 of 7")).toBeInTheDocument();
    expect(within(report as HTMLElement).getByRole("link", { name: /Critical: TRUST_NAV/ })).toHaveClass("ds-action--inset");
    expect(screen.getByRole("link", { name: /blueprint waits/ })).toHaveAttribute("href", "/centre/build/blueprint");
    expect(screen.getByText(/1 signature · 1 invite · 1 other thing · about 9 minutes/)).toBeInTheDocument(); // the critical line has no gap: id
    expect(screen.getByRole("link", { name: "Open the trace" })).toHaveAttribute("href", "/centre/intent/graph");
    expect(screen.getByText(/written from the day.s data runs/)).toBeInTheDocument();
  });

  test("sponsor: decide, the initiatives table with hurdle and who clears it, then watch", async () => {
    const { container } = open(base(["sponsor"], {
      layout: "sponsor",
      strips: [
        { key: "decide", lines: [line("sg", "signature", "A charter waits for your signature", "/centre/intent/charter/s1", "Review and sign"),
          line("p1", "decision", "Capital calls: one sentence on what the wall is for", "/centre/intent", "Write it")] },
        { key: "watch", lines: [line("b", "brief", "Singapore family offices: new reporting guidance", "/centre/consume/market", "Read")] },
      ],
      panels: {
        initiatives: [{ name: "Treasury", where: "Define: charter ready to sign", hurdle: null, who: "You", href: "/centre/intent/charter/s1" },
          { name: "Capital calls", where: "Waiting to start", hurdle: "Your purpose line", who: "You", href: "/centre/intent" }],
        watch: [{ label: "Measures released", value: "14 of 20", note: "6 wait on the trial" }, notYet("People's time this quarter")],
      },
    }));
    await screen.findByText(/Your initiatives/);
    expect(labels(container)).toEqual(["Decide", "Your initiatives", "Watch"]);
    expect(screen.getAllByRole("columnheader").map((h) => h.textContent)).toEqual(["Initiative", "Where it is", "Hurdle", "Who clears it"]);
    expect(screen.getByRole("link", { name: "Treasury" })).toHaveAttribute("href", "/centre/intent/charter/s1");
    expect(screen.getByText("Your purpose line")).toHaveClass("ds-warn");
    expect(screen.getByText("14 of 20")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Write one line" })).toBeInTheDocument();
    expect(screen.getByText(/1 signature · 1 other thing · about 6 minutes/)).toBeInTheDocument(); // the Watch brief is not a thing that needs you
  });

  test("empty: nothing needs you, the role's centres; phone tab bar carries the role's centres", async () => {
    const { container } = open(base(["owner"], { layout: "participant", map: { new_this_week: [], owned_changes: 0, owned_new: 0 } }));
    expect(await screen.findByText("Nothing needs you today.")).toBeInTheDocument();
    const empty = container.querySelector(".ds-empty") as HTMLElement;
    expect(within(empty).getByRole("link", { name: "Consume Centre" })).toHaveAttribute("href", "/centre/consume");
    expect(within(empty).queryByRole("link", { name: "Build Centre" })).toBeNull();
    const tabs = container.querySelector(".ds-tabbar") as HTMLElement;
    expect(within(tabs).getAllByRole("link").map((a) => a.textContent)).toEqual(["Pulse", "Intent", "Consume", "TICKETS", "Map"]);
    expect(within(tabs).getByRole("link", { name: "Pulse" })).toHaveAttribute("aria-current", "page");
    expect(container.querySelector(".ds-frame__aside")?.previousElementSibling).toHaveClass("ds-frame__main"); // stacks under 900px
  });
});
