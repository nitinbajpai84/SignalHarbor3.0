import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import BaselineSteps from "./BaselineSteps";
import { m2Steps } from "./copy";

const BID = "a".repeat(32);

describe("baseline step bar", () => {
  it("links to the work list, requests, process map, catalogue and sign-off of that baseline", () => {
    render(<MemoryRouter initialEntries={[`/modules/m2_baseline/catalogue/${BID}`]}><BaselineSteps baselineId={BID} /></MemoryRouter>);
    const to = (l: string) => screen.getByRole("link", { name: l }).getAttribute("href");
    expect(to(m2Steps.workList)).toBe(`/modules/m2_baseline/baselines/${BID}`);
    expect(to(m2Steps.requests)).toBe(`/modules/m2_baseline/requests/${BID}`);
    expect(to(m2Steps.processMap)).toBe(`/modules/m2_baseline/process-map/${BID}`);
    expect(to(m2Steps.catalogue)).toBe(`/modules/m2_baseline/catalogue/${BID}`);
    expect(to(m2Steps.governance)).toBe(`/modules/m2_baseline/governance/${BID}`);
    expect(to(m2Steps.signoff)).toBe(`/modules/m2_baseline/signoff/${BID}`);
    expect(screen.getByRole("link", { name: m2Steps.catalogue }).className).toContain("active");
    expect(screen.queryByText(m2Steps.signed)).toBeNull();
  });

  it("shows one read-only banner when the baseline is signed", () => {
    render(<MemoryRouter><BaselineSteps baselineId={BID} signed /></MemoryRouter>);
    expect(screen.getByRole("status")).toHaveTextContent("Signed: read-only");
  });
});
