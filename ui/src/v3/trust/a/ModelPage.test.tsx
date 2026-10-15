import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import ModelPage from "../ModelPage";
import { json, language, model, noPack, packs } from "./fixtures";

vi.mock("../../../useSession", () => ({ useSession: () => ({ user: { display_name: "Anita" } }) }));
afterEach(() => vi.unstubAllGlobals());
const route = (m: unknown) => vi.fn(async (u: string) => json(u.endsWith("/packs") ? packs : u.endsWith("/language") ? language : m));
const page = () => render(<MemoryRouter><ModelPage /></MemoryRouter>);

test("three layers, day one and other industries", async () => {
  vi.stubGlobal("fetch", route(model));
  page();
  expect(await screen.findByText("dry powder")).toBeInTheDocument();
  expect(screen.getByRole("region", { name: "Learned here, stays here" })).toHaveTextContent("Commitment");
  expect(screen.getByRole("region", { name: "Comes with the pack" })).toHaveTextContent("Entity");
  expect(screen.getByText("92% placed by themselves, 1 asked")).toBeInTheDocument();
  expect(screen.getByText("Insurance")).toBeInTheDocument();
});

test("no pack is an honest empty state; an error offers a retry", async () => {
  vi.stubGlobal("fetch", route(noPack));
  const { unmount } = page();
  expect(await screen.findByText("No industry model yet")).toBeInTheDocument();
  unmount();
  vi.stubGlobal("fetch", vi.fn(async () => json({}, false)));
  page();
  expect(await screen.findByRole("button", { name: "Try again" })).toBeInTheDocument();
});
