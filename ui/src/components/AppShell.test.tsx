import { render, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";

import AppShell from "./AppShell";

const getCompany = vi.fn();
vi.mock("../api/client", () => ({ getCompany: () => getCompany() }));
vi.mock("../useSession", () => ({ useSession: () => ({ signOut: vi.fn() }) }));
vi.mock("./NavRail", () => ({ default: () => null }));
vi.mock("./ThemeControl", () => ({ default: () => null }));
vi.mock("./BrandMark", () => ({ default: () => <span data-testid="sh-mark" /> }));

// A company with a brand record shows its logo beside its name; Signal Harbor's own mark stays; no brand shows no logo.

test("shows the company logo beside the name when the company has one", async () => {
  getCompany.mockResolvedValue({ company_id: "co", name: "Illustrative Harbour Office", industry: "x", brand: { logo: "logo.svg" } });
  const { container } = render(<AppShell>page</AppShell>);
  await screen.findByText("Illustrative Harbour Office");
  await waitFor(() => expect(container.querySelector("img.n-company-logo")).toHaveAttribute("src", "/api/company/logo"));
  expect(screen.getByTestId("sh-mark")).toBeInTheDocument();
});

test("shows no logo when the company has none", async () => {
  getCompany.mockResolvedValue({ company_id: "co", name: "Plain Co", industry: "x" });
  const { container } = render(<AppShell>page</AppShell>);
  await screen.findByText("Plain Co");
  expect(container.querySelector("img.n-company-logo")).toBeNull();
});
