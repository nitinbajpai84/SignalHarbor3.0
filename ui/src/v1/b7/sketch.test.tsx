import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import SketchPanel from "./SketchPanel";

const json = (body: unknown) => new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
const BOXES = [
  { id: "b1", label: "Net worth trend", row: 0, col: 0, status: "possible", why: "line by month" },
  { id: "b2", label: "Best / worst managers", row: 1, col: 0, status: "needs_definition", why: "fund league", question: "alpha this month or year to date?" },
  { id: "b3", label: "ESG score?", row: 1, col: 1, status: "not_possible", why: "no ESG data source" },
];
function setup() {
  const calls: { url: string; body: Record<string, unknown> }[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    const body = init?.body ? JSON.parse(String(init.body)) : {};
    calls.push({ url, body });
    if (url.endsWith("/sketch/build")) return json({ placed: 1, step: 3 });
    if (url.endsWith("/sketch/request")) return json({ request_id: "REQ-7" });
    return json({ boxes: BOXES });
  }));
  const onChanged = vi.fn();
  render(<SketchPanel pid="EV-1" did="d1" onChanged={onChanged} />);
  return { calls, onChanged };
}

describe("SketchPanel", () => {
  it("reads a picture, shows pills, builds and requests", async () => {
    const { calls, onChanged } = setup();
    const u = userEvent.setup();
    await u.upload(screen.getByLabelText("Sketch picture"), new File(["x"], "s.png", { type: "image/png" }));
    await u.click(screen.getByRole("button", { name: "Read my sketch" }));
    expect(await screen.findByText("POSSIBLE TODAY")).toBeInTheDocument();
    expect(screen.getByText("NEEDS A DEFINITION")).toBeInTheDocument();
    expect(screen.getByText("NOT POSSIBLE YET", { selector: "span" })).toBeInTheDocument();
    expect(screen.getByText(/alpha this month or year to date/)).toBeInTheDocument();
    expect(calls[0]!.url).toBe("/api/v1/build/p/EV-1/studio/d1/sketch");
    expect(calls[0]!.body.name).toBe("s.png");
    await u.click(screen.getByRole("button", { name: "Build the 1 possible now" }));
    await waitFor(() => expect(onChanged).toHaveBeenCalled());
    expect(calls[1]!.body).toEqual({ boxes: BOXES.filter((b) => b.status === "possible") });
    await u.click(screen.getByRole("button", { name: "Ask the data team for the 1 missing" }));
    expect(await screen.findByText(/REQ-7/)).toBeInTheDocument();
  });

  it("sends typed labels", async () => {
    const { calls } = setup();
    const u = userEvent.setup();
    await u.type(screen.getByLabelText(/Type the boxes instead/), "Net worth trend{enter}ESG score?");
    await u.click(screen.getByRole("button", { name: "Read these boxes" }));
    await screen.findByText("POSSIBLE TODAY");
    expect(calls[0]!.body).toEqual({ labels: ["Net worth trend", "ESG score?"] });
  });
});
