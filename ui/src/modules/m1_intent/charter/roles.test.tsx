import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import RolesPanel from "./RolesPanel";

// R1: the six roles with their mark and source; only the organiser edits.
const json = (body: unknown) => new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
const roles = (can_edit: boolean) => ({
  roles: { architect: "Dan Data", developer: "Eli Code", tester: null, sponsor: "Sue Sponsor", ops: null, informed: ["Ann"] },
  provenance: {
    architect: { mark: "guessed", by: "Lens", from: "The profile names the head of data: Dan Data" },
    sponsor: { mark: "stated", by: "Ann Example", from: "Set by the organiser" },
  },
  can_edit,
});
const calls: { method: string; body: unknown }[] = [];
function mock(can_edit: boolean) {
  calls.length = 0;
  vi.stubGlobal("fetch", vi.fn(async (_u: string, init?: RequestInit) => {
    const method = init?.method ?? "GET";
    calls.push({ method, body: init?.body ? JSON.parse(String(init.body)) : null });
    const stated = { mark: "stated", by: "Ann Example", from: "Set by the organiser" };
    const put = { ...roles(true), roles: { ...roles(true).roles, tester: "Tia Test" }, provenance: { ...roles(true).provenance, architect: stated, ops: stated } };
    return json(method === "PUT" ? put : roles(can_edit));
  }));
}

it("shows the six roles with their mark and source, and no edit for others", async () => {
  mock(false);
  render(<RolesPanel sessionId={"a".repeat(32)} />);
  expect(await screen.findByText("Dan Data")).toBeInTheDocument();
  for (const l of ["Architect", "Developer", "Tester", "Sponsor", "Operations", "Kept informed"]) expect(screen.getByText(l)).toBeInTheDocument();
  expect(screen.getByText(/Guessed\. The profile names the head of data/)).toBeInTheDocument();
  expect(screen.getByText("Named by Ann Example, the organiser.")).toBeInTheDocument();
  expect(screen.getByText("Stated", { selector: "[data-role=sponsor] span" })).toBeInTheDocument();
  expect(screen.queryByText(/Set by the organiser/)).toBeNull();
  expect(screen.getByText("These people get the Build hand-overs in their Pulse.")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /Edit/ })).toBeNull();
});

it("lets the organiser name a role", async () => {
  mock(true);
  render(<RolesPanel sessionId={"a".repeat(32)} />);
  await userEvent.click(await screen.findByRole("button", { name: "Edit Tester" }));
  await userEvent.type(screen.getByLabelText("Tester"), "Tia Test");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  expect(await screen.findByText("Tia Test")).toBeInTheDocument();
  expect(calls.at(-1)).toEqual({ method: "PUT", body: { tester: "Tia Test" } });
});

it("lets the organiser confirm a role Lens guessed", async () => {
  mock(true);
  render(<RolesPanel sessionId={"a".repeat(32)} />);
  await userEvent.click(await screen.findByRole("button", { name: "Confirm Architect" }));
  expect(calls.at(-1)).toEqual({ method: "PUT", body: { architect: "Dan Data" } });
  // the server's answer marks it stated: the mark turns and the Confirm button goes
  expect(await screen.findByText("Stated", { selector: "[data-role=architect] span" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Confirm Architect" })).toBeNull();
  expect(screen.queryByRole("button", { name: "Confirm Sponsor" })).toBeNull();
});

it("a role the organiser left empty reads as left open, not as stated", async () => {
  mock(true);
  render(<RolesPanel sessionId={"a".repeat(32)} />);
  await userEvent.click(await screen.findByRole("button", { name: "Confirm Architect" }));
  expect(await screen.findByText("Left open", { selector: "[data-role=ops] span" })).toBeInTheDocument();
});
