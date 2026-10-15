import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import SetupPage from "./SetupPage";
import { json, routes } from "./testFetch";

vi.mock("../../useSession", () => ({ useSession: () => ({ user: { display_name: "Anita" } }) }));
afterEach(() => vi.unstubAllGlobals());

const steps = [
  { id: "pack", label: "Pick your industry", done: false, detail: "" },
  { id: "files", label: "Files arrive", done: false, detail: "No files yet" },
];
const packs = { packs: [{ id: "insurance", label: "Insurance", objects: 8, questions: 12 }], current: "" };
const page = () => render(<MemoryRouter><SetupPage /></MemoryRouter>);

test("shows the real steps and a 409 in plain words", async () => {
  vi.stubGlobal("fetch", routes({
    "/api/v3/setup": () => json({ steps, pack: null }), "/api/v3/packs": () => json(packs),
    "POST /api/v3/setup": () => json({ detail: "Your office already has an industry pack." }, 409),
  }));
  page();
  expect(await screen.findByText("Pick your industry")).toBeInTheDocument();
  expect(screen.getByText("0 of 2 done")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Continue to the first question" })).toHaveAttribute("href", "/v3/start");
  await userEvent.click(screen.getByRole("button", { name: "Insurance" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Your office already has an industry pack.");
});

test("choosing a pack updates the timeline", async () => {
  vi.stubGlobal("fetch", routes({
    "/api/v3/setup": () => json({ steps, pack: null }), "/api/v3/packs": () => json(packs),
    "POST /api/v3/setup": () => json({ steps: [{ ...steps[0], done: true, detail: "Industry pack: Insurance" }, steps[1]], pack: { id: "insurance", label: "Insurance" } }),
  }));
  page();
  await userEvent.click(await screen.findByRole("button", { name: "Insurance" }));
  expect(await screen.findByText(/Industry pack: Insurance/)).toBeInTheDocument();
  expect(screen.getByText("1 of 2 done")).toBeInTheDocument();
});

test("no steps is an empty state", async () => {
  vi.stubGlobal("fetch", routes({ "/api/v3/setup": () => json({ steps: [], pack: null }) }));
  page();
  expect(await screen.findByText("There are no setup steps yet.")).toBeInTheDocument();
});

test("an error offers a retry", async () => {
  vi.stubGlobal("fetch", routes({}));
  page();
  expect(await screen.findByRole("button", { name: "Try again" })).toBeInTheDocument();
});
