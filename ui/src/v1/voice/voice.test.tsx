import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useState } from "react";

import { Composer, forgetVoice, NOT_AVAILABLE, SpeakButton, useReadAloud } from ".";

// V1 Voice against v1_voice_routes (docs/plan/v1-landings/V1.md). fetch is stubbed; the recorder (MediaRecorder behind it) is mocked.
vi.mock("../../modules/m1_intent/voice/recorder", () => ({ recordWav: vi.fn(async () => new Blob([new Uint8Array([82, 73, 70, 70])])) }));

const json = (body: unknown) => new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
function mock(available: boolean) {
  const calls: { url: string; body: unknown }[] = [];
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    calls.push({ url, body: init?.body ? JSON.parse(String(init.body)) : null });
    if (url === "/api/v1/voice") return json(available ? { available: true, note: null } : { available: false, note: NOT_AVAILABLE });
    if (url === "/api/v1/voice/transcribe") return json({ text: "Cash drag first" });
    return json({ audio: "UklGRg==", mime: "audio/wav", clipped: false });
  }));
  const play = vi.fn(async () => undefined);
  vi.stubGlobal("Audio", vi.fn(function Audio() { return { play, pause: vi.fn() }; }));
  return { calls, play };
}

function Box({ onSend }: { onSend: (t: string, f: File[]) => void }) {
  const [text, setText] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  return <Composer agent="North" text={text} setText={setText} files={files} setFiles={setFiles} onSend={onSend} />;
}

function Reader({ last }: { last: { id: string; text: string } }) {
  useReadAloud(last);
  return null;
}

beforeEach(() => { forgetVoice(); localStorage.clear(); });
afterEach(() => vi.unstubAllGlobals());

test("speaking puts the words in the box to read and send; the switch sends them by itself", async () => {
  const { calls } = mock(true);
  const sent = vi.fn();
  render(<Box onSend={sent} />);
  fireEvent.click(await screen.findByRole("button", { name: "Speak to North" }));
  expect(screen.getByRole("button", { name: "Stop and write it down" })).toBeInTheDocument();
  await waitFor(() => expect(screen.getByLabelText("Your message")).toHaveValue("Cash drag first"));
  expect(calls.find((c) => c.url === "/api/v1/voice/transcribe")?.body).toMatchObject({ mime: "audio/wav" });
  expect(sent).not.toHaveBeenCalled();

  fireEvent.click(screen.getByLabelText("Send automatically after speaking"));
  expect(localStorage.getItem("sh-v1-send-after-speaking")).toBe("1");
  fireEvent.click(screen.getByRole("button", { name: "Speak to North" }));
  await waitFor(() => expect(sent).toHaveBeenCalledWith("Cash drag first Cash drag first", []));
});

test("a play button reads a message aloud, and read-aloud speaks each new reply", async () => {
  const { calls, play } = mock(true);
  const { rerender } = render(<><SpeakButton text="Hello, I am North." /><Reader last={{ id: "t1", text: "Old reply" }} /></>);
  fireEvent.click(await screen.findByRole("button", { name: "Read this aloud" }));
  await waitFor(() => expect(play).toHaveBeenCalledTimes(1));
  expect(calls.filter((c) => c.url === "/api/v1/voice/speak").map((c) => c.body)).toEqual([{ text: "Hello, I am North." }]);

  render(<Box onSend={vi.fn()} />);
  fireEvent.click(await screen.findByLabelText("Read replies aloud"));
  expect(localStorage.getItem("sh-v1-read-aloud")).toBe("1");
  rerender(<><SpeakButton text="Hello, I am North." /><Reader last={{ id: "t2", text: "New reply" }} /></>);
  await waitFor(() => expect(calls.filter((c) => c.url === "/api/v1/voice/speak").map((c) => c.body)).toContainEqual({ text: "New reply" }));
  expect(calls.map((c) => c.body)).not.toContainEqual({ text: "Old reply" });
});

test("without voice the screen says so in one line and carries on in text; a picture goes by name only", async () => {
  mock(false);
  const sent = vi.fn();
  render(<><Box onSend={sent} /><SpeakButton text="Hi" /></>);
  expect(await screen.findByText(NOT_AVAILABLE)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Speak to North" })).toBeDisabled();
  expect(screen.queryByRole("button", { name: "Read this aloud" })).not.toBeInTheDocument();
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();

  const pic = new File(["x"], "board.png", { type: "image/png" });
  const csv = new File(["a,b\n1,2\n"], "cash.csv", { type: "text/csv" });
  await act(async () => { fireEvent.drop(screen.getByRole("form", { name: "Message North" }), { dataTransfer: { files: [pic, csv] } }); });
  expect(screen.getByText(/North can't read this type yet \(board\.png\); paste the text/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Send" }));
  expect(sent).toHaveBeenCalledWith("I added board.png.", [csv]);
});
