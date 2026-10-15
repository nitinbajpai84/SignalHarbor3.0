import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import RoleSuggest from "./RoleSuggest";

afterEach(() => vi.unstubAllGlobals());
const json = (b: unknown) => new Response(JSON.stringify(b), { status: 200, headers: { "Content-Type": "application/json" } });
const roles = [{ id: "cfo", title: "Head of Finance" }];
const build = (started: string | null) => ({ id: "uc6", title: "Capital calls", say: "Can each entity meet its calls?", dashboard: "Consume: cash by entity", skills: [], started });
const mine = (started: string | null) => ({ role: roles[0], actions: ["Approve funding"], builds: [build(started)], roles });
const page = () => render(<MemoryRouter><Routes><Route path="/" element={<RoleSuggest />} /><Route path="/v3/build/:id" element={<p>thread page</p>} /></Routes></MemoryRouter>);

test("Start this starts the thread and opens it", async () => {
  const f = vi.fn(async (u: string, i?: RequestInit) => json(i?.method === "POST" ? { id: "t9" } : mine(null)));
  vi.stubGlobal("fetch", f);
  page();
  expect(await screen.findByText("For you, Head of Finance")).toBeInTheDocument();
  expect(screen.getByText("suggested")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Start this" }));
  expect(await screen.findByText("thread page")).toBeInTheDocument();
  expect(JSON.parse(String(f.mock.calls.find((c) => String(c[0]).endsWith("/api/v3/threads"))?.[1]?.body))).toEqual({ text: "Can each entity meet its calls?" });
});

test("a started build shows Open", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => json(mine("t5"))));
  page();
  await userEvent.click(await screen.findByRole("button", { name: "Open" }));
  expect(await screen.findByText("thread page")).toBeInTheDocument();
});

test("no job asks for the role and posts it", async () => {
  const f = vi.fn(async (_u: string, i?: RequestInit) => json(i?.method === "POST" ? mine(null) : { role: null, actions: [], builds: [], roles }));
  vi.stubGlobal("fetch", f);
  page();
  await userEvent.selectOptions(await screen.findByLabelText("Your role"), "cfo");
  await waitFor(() => expect(screen.getByText("For you, Head of Finance")).toBeInTheDocument());
  expect(JSON.parse(String(f.mock.calls.find((c) => c[1]?.method === "POST")?.[1]?.body))).toEqual({ email: "", role: "cfo" });
});

test("no pack renders nothing", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => json({ role: null, actions: [], builds: [], roles: [] })));
  const { container } = page();
  await waitFor(() => expect(container).toBeEmptyDOMElement());
});
