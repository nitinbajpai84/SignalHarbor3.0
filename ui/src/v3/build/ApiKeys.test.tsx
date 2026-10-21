import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, test, vi } from "vitest";

import ApiKeys from "./ApiKeys";

const listApiKeys = vi.fn();
const makeApiKey = vi.fn();
const revokeApiKey = vi.fn();
vi.mock("../api", () => ({
  listApiKeys: () => listApiKeys(),
  makeApiKey: (...a: unknown[]) => makeApiKey(...a),
  revokeApiKey: (...a: unknown[]) => revokeApiKey(...a),
  setApiWebhook: vi.fn(),
  clearApiWebhook: vi.fn(),
}));
vi.mock("../Frame", () => ({ default: ({ children }: { children: ReactNode }) => <div>{children}</div> }));

const key = { id: "k1", label: "Reporting tool", kind: "company", member: null, scopes: ["figures", "signals"], entity_ids: [], rate_per_min: 60, created: "2026-10-20T08:00:00Z", revoked: false, webhook: null };
const at = () => render(<MemoryRouter><ApiKeys /></MemoryRouter>);

beforeEach(() => {
  vi.clearAllMocks();
  listApiKeys.mockResolvedValue({ keys: [], scopes: ["figures", "ask", "signals", "documents"], calls: [] });
});

test("empty: says there is no key yet and the make button waits for a name", async () => {
  at();
  expect(await screen.findByText("No key yet.")).toBeTruthy();
  expect((screen.getByRole("button", { name: "Make the key" }) as HTMLButtonElement).disabled).toBe(true);
});

test("a new key is shown once, with its text", async () => {
  makeApiKey.mockResolvedValue({ ...key, key: "shpub.evergreen.k1.secret" });
  at();
  await screen.findByText("No key yet.");
  fireEvent.change(screen.getByLabelText(/Name \(the tool it is for\)/), { target: { value: "Reporting tool" } });
  fireEvent.click(screen.getByRole("button", { name: "Make the key" }));
  expect(await screen.findByText("shpub.evergreen.k1.secret")).toBeTruthy();
  expect(makeApiKey).toHaveBeenCalledWith(expect.objectContaining({ label: "Reporting tool", scopes: ["figures"], kind: "company" }));
});

test("populated: lists the key and its recent call; revoke asks first", async () => {
  listApiKeys.mockResolvedValue({ keys: [key], scopes: [], calls: [{ key: "k1", route: "GET /api/public/v1/figures", at: "2026-10-20T08:01:00Z", status: 200 }] });
  revokeApiKey.mockResolvedValue({ revoked: true });
  vi.spyOn(window, "confirm").mockReturnValue(true);
  at();
  expect(await screen.findByRole("article", { name: "Reporting tool" })).toBeTruthy();
  expect(screen.getByText("GET /api/public/v1/figures")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Revoke" }));
  await waitFor(() => expect(revokeApiKey).toHaveBeenCalledWith("k1"));
});

test("error: a failed load says so and offers another try", async () => {
  listApiKeys.mockRejectedValueOnce(new Error("Please try again."));
  at();
  expect(await screen.findByRole("alert")).toBeTruthy();
});
