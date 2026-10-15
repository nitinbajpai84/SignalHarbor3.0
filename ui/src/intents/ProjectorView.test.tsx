import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { readFileSync } from "node:fs";

import ProjectorView from "./views/ProjectorView";
import BottomBar from "./BottomBar";

// The projector (spec 17). fetch is stubbed with synthetic data; the names and idea text below must never reach the screen.

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const INTENT = {
  state: "in_session", live: true,
  time_box: { ends: new Date(Date.now() + 25 * 60000).toISOString() },
  people: { organiser: "Janet Shaw", participants: ["Aaron Lyle", "Katie", "Harvey"] },
  session: { current_question: { text: "What do we track by hand today?", set_by: "Janet Shaw" } },
  share: { short: "k7m2qx" },
  refs: { wall_session_ids: ["s1"] },
  cards: [{ text: "Secret idea about the Tan trust", author: "Aaron Lyle" }],
};

const WALL = { role: "organiser", counts: { total: 5, per_lane: { intent: 2, pain_point: 3, future_signal: 0, lever: 0 } }, people: { invited: 4, joined: 3 } };

function mock(intent: unknown, status = 200, wall: unknown = WALL) {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    if (url.endsWith("/wall")) return json(status, wall);
    if (url.startsWith("/api/intents/i1")) return json(status, intent);
    return json(200, {});
  }));
}
function view() {
  return render(
    <MemoryRouter initialEntries={["/centre/intent/i1/projector"]}>
      <Routes>
        <Route path="/centre/intent/:intentId/projector" element={<ProjectorView />} />
        <Route path="/centre/intent/:intentId" element={<p>intent screen</p>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("projector view", () => {
  it("shows counts, question, clock and the join link, and no name or idea text", async () => {
    mock(INTENT);
    const { container } = view();
    await waitFor(() => expect(screen.getByTestId("count-pain_point")).toHaveTextContent("3"));
    expect(screen.getByTestId("question")).toHaveTextContent("What do we track by hand today?");
    expect(screen.getByTestId("clock").textContent).toMatch(/^2[34]:\d\d$/);
    expect(screen.getByTestId("join")).toHaveTextContent(/Join: .*\/join\/k7m2qx/);
    expect(screen.getByTestId("people")).toHaveTextContent("3 / 4 people");
    const text = container.textContent ?? "";
    for (const hidden of ["Janet", "Aaron", "Katie", "Harvey", "Secret idea", "Tan trust"]) expect(text).not.toContain(hidden);
  });

  it("says so when there is no question, no end and no sharing, and never shows a lane count it cannot read", async () => {
    mock({ ...INTENT, session: null, time_box: null, share: null }, 200, { role: "organiser", counts: null, people: null });
    view();
    await waitFor(() => expect(screen.getByTestId("question")).toHaveTextContent("No question is set yet."));
    expect(screen.getByTestId("clock")).toHaveTextContent("The session has no end set.");
    expect(screen.getByTestId("join")).toHaveTextContent("Turn on sharing to show the join code.");
    expect(screen.getByTestId("count-intent")).toHaveTextContent("Not available yet");
  });

  it("returns a refused caller to the intent screen", async () => {
    mock({ error: "forbidden" }, 403);
    view();
    await waitFor(() => expect(screen.getByText("intent screen")).toBeInTheDocument());
  });
});

describe("who may open it", () => {
  it("sends a participant back to the intent screen and shows nothing of the join box", async () => {
    mock(INTENT, 200, { ...WALL, role: "participant" });
    const { container } = view();
    await waitFor(() => expect(screen.getByText("intent screen")).toBeInTheDocument());
    expect(container.textContent).not.toContain("k7m2qx");
  });
});

describe("phone rules", () => {
  it("the bottom bar and the sheet carry the shared phone classes", () => {
    const { container } = render(<BottomBar><button className="ds-btn">One</button></BottomBar>);
    expect(container.querySelector("nav.ic-bar")).not.toBeNull();
    const css = readFileSync("src/intents/phone.css", "utf-8");
    expect(css).toMatch(/\.ic-bar \.ds-btn \{[^}]*min-height: 48px/);
    expect(css).toMatch(/\.ic-phone \.ds-btn[^{]*\{[^}]*min-height: 44px/);
    expect(css).toMatch(/\.ic-sheet \{[^}]*max-height: 80vh/);
  });
});
