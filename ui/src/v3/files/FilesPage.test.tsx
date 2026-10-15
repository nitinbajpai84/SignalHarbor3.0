import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import type { FileRow } from "../api";
import FilesPage, { bySource } from "./FilesPage";

const api = vi.hoisted(() => ({ listFiles: vi.fn(), getConnections: vi.fn() }));
const up = vi.hoisted(() => ({ postFile: vi.fn(), filesFromDrop: vi.fn() }));
vi.mock("../api", () => api);
vi.mock("./upload", () => up);
vi.mock("../../useSession", () => ({ useSession: () => ({ user: { display_name: "Test Person" } }) }));

const row = (name: string, status: FileRow["status"], source = "", at = "2026-10-03T07:12:00Z"): FileRow => ({ name, status, source, arrived_at: at, thread: "" });
const mount = () => render(<MemoryRouter><FilesPage /></MemoryRouter>);

beforeEach(() => {
  vi.resetAllMocks();
  api.getConnections.mockResolvedValue({ connections: [{ id: "m", kind: "mailbox", name: "Mail", target: "files@sample.test", schedule: "", last_pull: "", state: "ok" }] });
});

describe("FilesPage", () => {
  it("lists files with pills, a question card, sources seen and the mailbox from connections", async () => {
    api.listFiles.mockResolvedValue({ files: [row("Bank Sep.pdf", "loaded", "Bank"), row("Bank Aug.pdf", "recognised", "Bank", "2026-09-03T07:00:00Z"), row("Scan 0412.pdf", "question")] });
    mount();
    expect(await screen.findByText("Bank Sep.pdf")).toBeInTheDocument();
    expect(screen.getByText("Loaded")).toBeInTheDocument();
    expect(screen.getByText("What is this file?")).toBeInTheDocument();
    expect(screen.getByText("2 files")).toBeInTheDocument();
    expect(await screen.findByText("files@sample.test")).toBeInTheDocument();
  });

  it("shows the empty and error states", async () => {
    api.listFiles.mockResolvedValueOnce({ files: [] });
    mount();
    expect(await screen.findByText(/Nothing has arrived yet/)).toBeInTheDocument();
    api.listFiles.mockRejectedValueOnce(new Error("Harbor is not answering."));
    mount();
    expect(await screen.findByRole("alert")).toHaveTextContent("Harbor is not answering.");
  });

  it("uploads each chosen file and shows a reported duplicate as skipped", async () => {
    api.listFiles.mockResolvedValue({ files: [] });
    up.postFile.mockImplementation(async (f: File, onPct: (n: number) => void) => {
      onPct(50);
      return [{ ...row(f.name, "waiting"), skipped: f.name === "dup.csv" }];
    });
    mount();
    await screen.findByText(/Nothing has arrived yet/);
    const files = [new File(["a"], "new.csv"), new File(["b"], "dup.csv")];
    fireEvent.change(screen.getByLabelText("Choose files"), { target: { files } });
    expect(await screen.findByText("Duplicate, skipped")).toBeInTheDocument();
    expect(up.postFile).toHaveBeenCalledTimes(2);
    expect(screen.getByText(/dup.csv is the same as a file Harbor already has/)).toBeInTheDocument();
  });

  it("groups only sources that were seen", () => {
    expect(bySource([row("a", "waiting"), row("b", "loaded", "Custodian")])).toEqual([{ source: "Custodian", count: 1, last: "2026-10-03T07:12:00Z" }]);
  });
});
