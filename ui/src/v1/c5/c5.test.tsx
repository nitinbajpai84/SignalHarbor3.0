import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import { ThemeProvider } from "../../theme";
import { SessionProvider } from "../../useSession";
import ConnectorsPage from "./ConnectorsPage";

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
afterEach(() => vi.unstubAllGlobals());
vi.setConfig({ testTimeout: 20000 });

const conn = { id: "m1", kind: "imap", host: "mail.example.test", schedule: "daily", source_code: "custodian", file_pattern: "*.csv", credentials: { user: "MAIL_USER", password: "MAIL_PASS" }, params: { mailbox: "INBOX" },
  health: { status: "failed", failed: true, late: false, last_run: "2026-10-10T08:00:00+00:00", last_ok: null, last_files: 0, files_landed: 3, duplicates_skipped: 1, error: { code: "login_failed", message: "The mail server refused the sign-in or the folder." } } };

function mock(sent: string[], list: unknown[] = [conn]) {
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (url === "/api/auth/me") return json(200, { display_name: "Mei", company_id: "evergreen", roles: ["analyst"] });
    if (init?.method && init.method !== "GET") { sent.push(`${init.method} ${url} ${String(init.body ?? "")}`); return json(200, url.endsWith("/dry-run") ? { ok: true, would_arrive: [{ name: "a.csv", size: 3 }] } : { ok: true }); }
    if (url === "/api/v1/connectors") return json(200, { connectors: list, kinds: ["imap", "sftp", "graph"], schedules: ["manual", "daily"], egress_note: "Hosts must be on the internet list." });
    return json(404, { error: "not_found", message: "Not found." });
  }));
}
const wrap = () => render(<MemoryRouter><ThemeProvider><SessionProvider><ConnectorsPage /></SessionProvider></ThemeProvider></MemoryRouter>);

test("lists connectors with the state in words and the failure reason", async () => {
  mock([]);
  wrap();
  expect(await screen.findByText("Failed")).toBeInTheDocument();
  expect(screen.getByText("The mail server refused the sign-in or the folder.")).toBeInTheDocument();
  expect(screen.getByText("3")).toBeInTheDocument();
});

test("empty state, and Dry run shows what would arrive", async () => {
  mock([], []);
  const { unmount } = wrap();
  expect(await screen.findByText(/No connectors yet/)).toBeInTheDocument();
  unmount();
  const sent: string[] = [];
  mock(sent);
  wrap();
  await userEvent.click(await screen.findByRole("button", { name: "Dry run" }));
  expect(await screen.findByText(/1 file\(s\) would arrive: a.csv/)).toBeInTheDocument();
  expect(sent[0]).toMatch(/^POST \/api\/v1\/connectors\/m1\/dry-run/);
});

test("saving sends variable names, not secrets", async () => {
  const sent: string[] = [];
  mock(sent);
  wrap();
  await userEvent.type(await screen.findByLabelText("Name"), "m2");
  await userEvent.type(screen.getByLabelText("Host"), "mail.example.test");
  await userEvent.type(screen.getByLabelText(/Variable holding the user/), "mail_user");
  await userEvent.type(screen.getByLabelText(/Variable holding the password/), "mail_pass");
  await userEvent.type(screen.getByLabelText("Source code"), "custodian");
  await userEvent.click(screen.getByRole("button", { name: "Save connector" }));
  expect(sent[0]).toMatch(/^PUT \/api\/v1\/connectors\/m2 /);
  expect(sent[0]).toContain('"password":"MAIL_PASS"');
});
