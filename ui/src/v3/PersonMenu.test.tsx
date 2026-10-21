import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import PersonMenu from "./PersonMenu";

const signOut = vi.fn(async () => undefined);

const enable = vi.fn(async () => undefined);
const disable = vi.fn(async () => undefined);
let cfg = { enabled: true, public_key: "BKEY", subscribed: false };
vi.mock("../pwa", () => ({
  getPushConfig: async () => cfg, enablePush: (...a: unknown[]) => enable(...(a as [])), disablePush: () => disable(),
  pushSupported: () => true, installKind: () => "prompt", install: vi.fn(async () => true), onInstallChange: () => () => undefined,
}));

const open = async () => { render(<MemoryRouter><PersonMenu name="Sofia Reyes" /></MemoryRouter>); await userEvent.click(screen.getByRole("button", { name: "Sofia Reyes" })); };

test("the switch subscribes this device, and again switches it off", async () => {
  cfg = { enabled: true, public_key: "BKEY", subscribed: false };
  await open();
  const sw = await screen.findByRole("switch", { name: /Notifications/ });
  await userEvent.click(sw);
  expect(enable).toHaveBeenCalledWith("BKEY");
  expect(sw).toBeChecked();
  await userEvent.click(sw);
  expect(disable).toHaveBeenCalled();
});

test("the menu offers the family portal and Install app", async () => {
  await open();
  expect(screen.getByRole("menuitem", { name: "Family portal" })).toHaveAttribute("href", "/v3/portal");
  expect(screen.getByRole("menuitem", { name: "Install app" })).toBeInTheDocument();
});

test("a refused permission is explained, not hidden", async () => {
  cfg = { enabled: true, public_key: "BKEY", subscribed: false };
  enable.mockRejectedValueOnce(new Error("Notifications are blocked for this site."));
  await open();
  await userEvent.click(await screen.findByRole("switch", { name: /Notifications/ }));
  expect(await screen.findByRole("alert")).toHaveTextContent("blocked for this site");
});

test("with no keys on the server the switch is off and says why", async () => {
  cfg = { enabled: false, public_key: null as unknown as string, subscribed: false };
  await open();
  expect(await screen.findByText(/not switched on for this office/)).toBeInTheDocument();
  expect(screen.getByRole("switch")).toBeDisabled();
});

test("Sign out ends the session and lands on the login page", async () => {
  render(<MemoryRouter initialEntries={["/v3/desk"]}><Routes><Route path="/login" element={<p>Login page</p>} /><Route path="*" element={<PersonMenu name="Sofia Reyes" onSignOut={signOut} />} /></Routes></MemoryRouter>);
  await userEvent.click(screen.getByRole("button", { name: "Sofia Reyes" }));
  await userEvent.click(screen.getByRole("menuitem", { name: "Sign out" }));
  expect(signOut).toHaveBeenCalled();
  expect(await screen.findByText("Login page")).toBeInTheDocument();
});
