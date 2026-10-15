import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import type { ReactElement } from "react";

import { ActionCard, CheckIcon, EmptyState, MapColumns, PageFrame, Pill, TopBar, type PillTone } from ".";

const wrap = (ui: ReactElement) => render(<MemoryRouter>{ui}</MemoryRouter>);

describe("design parts", () => {
  it("TopBar shows the links, the active one marked, and the person with their role", () => {
    wrap(<TopBar product="Signal Harbor" company="Lakeside Family Office" person="Priya Nair" role="Participant" initials="PN"
      links={[{ label: "Pulse", href: "/p", active: true }, { label: "Map", href: "/m" }]} />);
    expect(screen.getByRole("link", { name: "Pulse" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Map" })).not.toHaveAttribute("aria-current");
    expect(screen.getByText("Priya Nair · Participant")).toBeInTheDocument();
    expect(screen.getByText("Lakeside Family Office")).toBeInTheDocument();
  });

  it("ActionCard is one link carrying the href, with title, detail and action word inside", () => {
    wrap(<ActionCard icon={<CheckIcon />} title="Confirm Fees Charged" detail="Drafted by Lens" action="Confirm" href="/centre/x" />);
    const links = screen.getAllByRole("link");
    expect(links).toHaveLength(1);
    expect(links[0]).toHaveAttribute("href", "/centre/x");
    expect(links[0]).toHaveTextContent("Confirm Fees Charged");
    expect(links[0]).toHaveTextContent("Drafted by Lens");
    expect(links[0]).toHaveTextContent("Confirm");
  });

  it("PageFrame puts the aside in its own column with the class the 900px rule stacks", () => {
    const { container } = wrap(<PageFrame title="Good morning, Priya." subline="4 things need you" aside={<p>side</p>}><p>main</p></PageFrame>);
    const frame = container.querySelector("main.ds-frame");
    expect(frame).not.toBeNull();
    expect(frame?.querySelector(":scope > section.ds-frame__main")).toHaveTextContent("main");
    expect(frame?.querySelector(":scope > aside.ds-frame__aside")).toHaveTextContent("side");
    expect(screen.getByRole("heading", { level: 1, name: "Good morning, Priya." })).toBeInTheDocument();
  });

  it("MapColumns draws one line per linked pair, skips links to unknown things, rings a hole and hides a restricted label", () => {
    const onSelect = vi.fn();
    const { container } = wrap(
      <MapColumns
        columns={[
          { title: "Problems", nodes: [{ id: "p1", label: "Fee leakage", kind: "problem" }, { id: "p2", label: "Pay bands", kind: "problem", restricted: true }] },
          { title: "Measures", nodes: [{ id: "m1", label: "Fees Charged", kind: "measure" }, { id: "m2", label: "Trust NAV", kind: "measure" }] },
        ]}
        edges={[{ from: "p1", to: "m1" }, { from: "p1", to: "m2" }, { from: "p2", to: "m2" }, { from: "p1", to: "gone" }]}
        holeIds={["m2"]} onSelect={onSelect}
      />,
    );
    expect(container.querySelectorAll(".ds-map__lines line")).toHaveLength(3);
    expect(container.querySelector('[data-id="m2"]')).toHaveClass("ds-node--hole");
    expect(container.querySelector('[data-id="m1"]')).not.toHaveClass("ds-node--hole");
    expect(screen.queryByText("Pay bands")).toBeNull();
    expect(screen.getByRole("img", { name: "Restricted" })).toHaveClass("ds-node--silhouette");
    fireEvent.mouseEnter(screen.getByRole("button", { name: "Fees Charged" }));
    expect(container.querySelectorAll("line.ds-edge--on")).toHaveLength(1);
    fireEvent.click(screen.getByRole("button", { name: "Trust NAV, no source yet" }));
    expect(onSelect).toHaveBeenCalledWith("m2");
  });

  it("Pill carries one class per tone", () => {
    const tones: PillTone[] = ["ok", "late", "failed", "draft", "signed", "open", "restricted"];
    wrap(<>{tones.map((t) => <Pill key={t} tone={t}>{t}</Pill>)}</>);
    for (const t of tones) expect(screen.getByText(t)).toHaveClass("ds-pill", `ds-pill--${t}`);
  });

  it("EmptyState shows its title, every line and its links", () => {
    wrap(<EmptyState title="Nothing needs you today" lines={["New asks appear here.", "Check back tomorrow."]} links={[{ label: "Open the map", href: "/m" }]} />);
    expect(screen.getByText("Nothing needs you today")).toBeInTheDocument();
    expect(screen.getByText("New asks appear here.")).toBeInTheDocument();
    expect(screen.getByText("Check back tomorrow.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open the map" })).toHaveAttribute("href", "/m");
  });
});
