import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import DownloadButton from "./DownloadButton";

// M2-FIX-N D13: a download fetches with the session, saves through a real <a download>, and releases the blob address.

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

function stub(res: Response | Promise<Response>) {
  vi.stubGlobal("fetch", vi.fn(async () => res));
  URL.createObjectURL = vi.fn(() => "blob:abc");
  URL.revokeObjectURL = vi.fn();
  const names: (string | null)[] = [];
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) {
    names.push(this.download);
    expect(this.href).toBe("blob:abc");
  });
  return names;
}

test("the file is named by the server, saved through an anchor and the blob address is released", async () => {
  const names = stub(new Response("xlsx", { status: 200, headers: { "Content-Disposition": 'attachment; filename="data-catalogue.xlsx"' } }));
  render(<DownloadButton path="/api/x/export" fallbackName="fallback.xlsx" label="Download" />);
  await userEvent.click(screen.getByRole("button", { name: "Download" }));
  await waitFor(() => expect(names).toEqual(["data-catalogue.xlsx"]));
  await waitFor(() => expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:abc"));
});

test("without a name from the server the fallback name is used", async () => {
  const names = stub(new Response("html", { status: 200 }));
  render(<DownloadButton path="/api/x/print" fallbackName="glossary.html" label="Print" />);
  await userEvent.click(screen.getByRole("button", { name: "Print" }));
  await waitFor(() => expect(names).toEqual(["glossary.html"]));
});

test("a refusal shows the server's plain sentence and nothing is saved", async () => {
  const names = stub(new Response(JSON.stringify({ message: "You do not have access to this." }), { status: 403, headers: { "Content-Type": "application/json" } }));
  render(<DownloadButton path="/api/x/export" fallbackName="a.xlsx" label="Download" />);
  await userEvent.click(screen.getByRole("button", { name: "Download" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("You do not have access to this.");
  expect(names).toEqual([]);
});
