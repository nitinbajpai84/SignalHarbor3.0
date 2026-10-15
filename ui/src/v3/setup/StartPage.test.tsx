import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { forgetVoice } from "../../v1/voice";
import StartPage from "./StartPage";
import { json, routes, voiceOff } from "./testFetch";

vi.mock("../../useSession", () => ({ useSession: () => ({ user: { display_name: "Anita" } }) }));
afterEach(() => { vi.unstubAllGlobals(); forgetVoice(); });

const page = () => render(
  <MemoryRouter initialEntries={["/v3/start"]}>
    <Routes><Route path="/v3/start" element={<StartPage />} /><Route path="/v3/thread/:id" element={<p>thread open</p>} /></Routes>
  </MemoryRouter>);

test("sending the brief starts a thread and opens it", async () => {
  const f = routes({ ...voiceOff, "/api/v3/setup": () => json({ steps: [], pack: null }), "POST /api/v3/threads": () => json({ id: "t1" }) });
  vi.stubGlobal("fetch", f);
  page();
  expect(await screen.findByText(/No industry pack is chosen yet/)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Attach sample files" })).toHaveAttribute("href", "/v3/files");
  expect(screen.getByText(/only three things/)).toBeInTheDocument();
  await userEvent.type(screen.getByLabelText("Say it in your own words"), "Are premiums in on time?");
  await userEvent.click(screen.getByRole("button", { name: "Send to Harbor" }));
  expect(await screen.findByText("thread open")).toBeInTheDocument();
  const post = f.mock.calls.find((c) => c[1]?.method === "POST");
  expect(String(post?.[1]?.body)).toContain("Are premiums in on time?");
});

test("a suggestion card starts its thread", async () => {
  vi.stubGlobal("fetch", routes({
    ...voiceOff, "/api/v3/setup": () => json({ steps: [], pack: { id: "insurance", label: "Insurance", intent_examples: ["Which claims are open?"] } }),
    "POST /api/v3/threads": () => json({ id: "t2" }),
  }));
  page();
  await userEvent.click(await screen.findByRole("button", { name: "Which claims are open?" }));
  expect(await screen.findByText("thread open")).toBeInTheDocument();
});

test("suggestions that fail to load offer a retry", async () => {
  vi.stubGlobal("fetch", routes(voiceOff));
  page();
  expect(await screen.findByRole("button", { name: "Try again" })).toBeInTheDocument();
});
