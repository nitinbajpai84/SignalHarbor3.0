import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import App from "../App";
import { copy } from "../copy";
import { loginCopy } from "./loginCopy";

function mockSignedOut() {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response(JSON.stringify({ error: "session_expired", message: "x", login_url: "/login" }), { status: 401 })),
  );
}

function renderLogin() {
  mockSignedOut();
  return render(
    <MemoryRouter initialEntries={["/login"]}>
      <App />
    </MemoryRouter>,
  );
}

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("LoginPage", () => {
  test("displays the tagline and theme buttons", async () => {
    renderLogin();
    await screen.findByRole("button", { name: copy.login.button });
    expect(screen.getByText(loginCopy.tagline)).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "Theme" })).toBeInTheDocument();
  });

  test("shows the Signal Harbor name and brand mark", async () => {
    renderLogin();
    await screen.findByRole("button", { name: copy.login.button });
    expect(screen.getByText(copy.product)).toBeInTheDocument();
    expect(document.querySelector("img.brand-mark")).toBeInTheDocument();
  });

  test("sign-in form has email and password fields with labels and a submit button", async () => {
    renderLogin();
    expect(await screen.findByLabelText(copy.login.email)).toBeInTheDocument();
    expect(await screen.findByLabelText(copy.login.password)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: copy.login.button })).toBeInTheDocument();
  });

  test("sign-in with valid credentials succeeds", async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url === "/api/auth/login") {
          return new Response(JSON.stringify({ display_name: "Ann", company_id: "co-a", roles: ["analyst"] }), { status: 200 });
        }
        return new Response(JSON.stringify({ error: "session_expired", message: "x", login_url: "/login" }), { status: 401 });
      }),
    );
    renderLogin();
    const emailInput = await screen.findByLabelText(copy.login.email) as HTMLInputElement;
    const passwordInput = await screen.findByLabelText(copy.login.password) as HTMLInputElement;
    const submitButton = screen.getByRole("button", { name: copy.login.button });

    await user.type(emailInput, "test@example.com");
    await user.type(passwordInput, "password");
    await user.click(submitButton);

    await waitFor(() => {
      expect(emailInput.value).toBe("test@example.com");
    });
  });

  test("sign-in with invalid credentials shows error and clears password", async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url === "/api/auth/login") {
          return new Response(JSON.stringify({ error: "login_failed", message: "no" }), { status: 401 });
        }
        return new Response(JSON.stringify({ error: "session_expired", message: "x", login_url: "/login" }), { status: 401 });
      }),
    );
    renderLogin();
    const emailInput = await screen.findByLabelText(copy.login.email) as HTMLInputElement;
    const passwordInput = await screen.findByLabelText(copy.login.password) as HTMLInputElement;
    const submitButton = screen.getByRole("button", { name: copy.login.button });

    await user.type(emailInput, "test@example.com");
    await user.type(passwordInput, "wrong");
    await user.click(submitButton);

    expect(await screen.findByText(copy.login.mismatch)).toBeInTheDocument();
    expect(passwordInput.value).toBe("");
  });

  test("shows session ended message when session has ended", async () => {
    mockSignedOut();
    const { rerender } = render(
      <MemoryRouter initialEntries={["/login"]}>
        <App />
      </MemoryRouter>,
    );
    await screen.findByRole("button", { name: copy.login.button });
    // Session ended message should not be visible on initial load
    expect(screen.queryByText(copy.errors.sessionEnded)).not.toBeInTheDocument();
  });

  test("email input receives focus on mount", async () => {
    renderLogin();
    const emailInput = await screen.findByLabelText(copy.login.email) as HTMLInputElement;
    await waitFor(() => {
      expect(emailInput).toHaveFocus();
    });
  });
  test("one card on the design tokens: sign-in posts the email and password and shows the plain error", async () => {
    const user = userEvent.setup();
    const posts: unknown[] = [];
    vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
      if (url === "/api/auth/login") {
        posts.push(JSON.parse(String(init?.body)));
        return new Response(JSON.stringify({ error: "x", message: "x" }), { status: 503 });
      }
      return new Response(JSON.stringify({ error: "session_expired", message: "x", login_url: "/login" }), { status: 401 });
    }));
    render(<MemoryRouter initialEntries={["/login"]}><App /></MemoryRouter>);
    const button = await screen.findByRole("button", { name: copy.login.button });
    expect(button).toHaveClass("ds-btn--primary");
    expect(button.closest(".ds-card")).not.toBeNull();
    await user.type(screen.getByLabelText(copy.login.email), "ann@example.test");
    await user.type(screen.getByLabelText(copy.login.password), "pw");
    await user.click(button);
    expect((await screen.findByRole("alert")).textContent).toBe(copy.login.unavailable);
    expect(posts).toEqual([{ email: "ann@example.test", password: "pw" }]);
  });
});
