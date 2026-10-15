import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import WelcomePage from "./WelcomePage";
import { json, routes } from "./testFetch";

vi.mock("../../useSession", () => ({ useSession: () => ({ user: { display_name: "Anita" } }) }));
afterEach(() => vi.unstubAllGlobals());

const people = { people: [{ name: "Ravi", role: "decides" }], second_signer: false, autonomy: [], ask_rules: [], usage: { questions: 0, builds: 0, mode: "testing" } };
const conns = { connections: [{ id: "drop", kind: "folder", name: "Drop folder", target: "", schedule: "", last_pull: "", state: "ok" }] };
const page = () => render(
  <MemoryRouter initialEntries={["/v3/welcome"]}>
    <Routes><Route path="/v3/welcome" element={<WelcomePage />} /><Route path="/v3/thread/:id" element={<p>thread open</p>} /></Routes>
  </MemoryRouter>);

test("shows people, sources and the pack's own suggestions, and starts a thread", async () => {
  vi.stubGlobal("fetch", routes({
    "/api/v3/people": () => json(people), "/api/v3/connections": () => json(conns),
    "/api/v3/setup": () => json({ steps: [], pack: { id: "insurance", label: "Insurance", intent_examples: ["Which claims are open?"] } }),
    "POST /api/v3/threads": () => json({ id: "t9" }),
  }));
  page();
  expect(await screen.findByText("Ravi")).toBeInTheDocument();
  expect(screen.getByText("Drop folder")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Manage connections" })).toHaveAttribute("href", "/v3/trust/connections");
  expect(screen.getByRole("link", { name: "Drop or upload files" })).toHaveAttribute("href", "/v3/files");
  expect(screen.getByText("Suggested from the Insurance pack")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Which claims are open?" }));
  await userEvent.click(screen.getByRole("button", { name: "Start" }));
  expect(await screen.findByText("thread open")).toBeInTheDocument();
});

test("a pack that ships no examples, and an empty office, say so", async () => {
  vi.stubGlobal("fetch", routes({
    "/api/v3/people": () => json({ ...people, people: [] }), "/api/v3/connections": () => json({ connections: [] }),
    "/api/v3/setup": () => json({ steps: [], pack: { id: "family_office", label: "Family office" } }),
    "/api/v3/packs": () => json({ packs: [], current: "family_office" }),
  }));
  page();
  expect(await screen.findByText(/has no suggested questions yet/)).toBeInTheDocument();
  expect(screen.getByText("No one has been added yet.")).toBeInTheDocument();
  expect(screen.getByText("Nothing is connected yet.")).toBeInTheDocument();
});

test("an error offers a retry", async () => {
  vi.stubGlobal("fetch", routes({}));
  page();
  expect(await screen.findByRole("button", { name: "Try again" })).toBeInTheDocument();
});
