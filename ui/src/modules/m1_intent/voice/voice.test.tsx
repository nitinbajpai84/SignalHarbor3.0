import { render, screen, waitFor, configure } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import App from "../../../App";
import { setSessionExpiredHandler } from "../../../api/client";
import { m1Voice as t } from "../copy";
import type { Room } from "../private_room/roomApi";
import { VOICE_DOWN, combineText } from "./VoiceControls";
import type { Voice } from "./voiceApi";

// M1-P06: the microphone flow with correction, the mute, the play button, the plain message when speech is not
// available, and the silent fallback. fetch, the recorder and the audio element are stubbed: nothing is recorded or heard.

vi.mock("./recorder", () => ({
  // finishes when the person presses stop (the signal aborts), like the real recorder
  recordWav: vi.fn(
    ({ signal }: { signal: AbortSignal }) =>
      new Promise<Blob>((resolve) => signal.addEventListener("abort", () => resolve(new Blob(["RIFFxxxxWAVE"], { type: "audio/wav" })))),
  ),
}));
import { recordWav } from "./recorder";

// These tests render the whole App; on a loaded machine the 1s default for findBy*/waitFor is too short.
configure({ asyncUtilTimeout: 5000 });

const SID = "a".repeat(32);
const BASE = `/api/modules/m1_intent/sessions/${SID}`;
const ROOM = `${BASE}/room`;
const VOICE = `${BASE}/voice`;
const ON: Voice = { available: true, on: true, message: null, note: "Speech to text is on", max_seconds: 120 };
const OFF_AIR: Voice = { available: false, on: true, message: t.unavailable, note: null, max_seconds: 120 };
const NORTH = { practice_on: false, library_on: false, available: true };
const room = (over: Partial<Room> = {}): Room => ({ title: "Illustrative session", form: [], open: true, message: null, turns: [], notes: [], north: NORTH, ...over });
const withNorth = room({
  turns: [
    { id: "t1", role: "person", text: "Renewals slipped", at: "x" },
    { id: "t2", role: "north", text: "Who is affected?", at: "x", answered: true },
  ],
});

interface World {
  voice?: Voice | 404;
  heard?: unknown;
  spoken?: unknown;
  room?: Room;
  after?: Room;
}
const calls: { method: string; url: string; body: unknown }[] = [];
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const played: string[] = [];

function mock(w: World) {
  calls.length = 0;
  played.length = 0;
  let voice = w.voice ?? ON;
  vi.stubGlobal("Audio", class { src: string; constructor(src: string) { this.src = src; } pause() {} play() { played.push(this.src); return Promise.resolve(); } });
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    const method = init?.method ?? "GET";
    const body = init?.body ? JSON.parse(String(init.body)) : undefined;
    calls.push({ method, url, body });
    if (url === "/api/auth/me") return json(200, { display_name: "Ann", company_id: "co-a", roles: ["company_admin"] });
    if (url === "/api/company") return json(200, { company_id: "co-a", name: "Harbor Test Co", industry: "none" });
    if (url === "/api/modules") return json(200, [{ id: "m1_intent", number: 1, name: "Intent", description: "d", agent: "North" }]);
    if (url === ROOM) return json(200, w.room ?? room());
    if (url.endsWith("/timer")) return json(200, { timed: false, stage: "private_rooms" }); // M1-UI1: the room shows the stage timer when there is one
    if (url === `${ROOM}/library`) return json(200, { on: false, available: false, label: "x", problems: [], message: "none" });
    if (url === VOICE && method === "GET") return voice === 404 ? json(404, {}) : json(200, voice);
    if (url === VOICE && method === "POST") {
      if (voice !== 404) voice = { ...voice, on: (body as { on: boolean }).on };
      return json(200, voice);
    }
    if (url === `${VOICE}/transcribe`) return w.heard === 500 ? json(500, {}) : json(200, w.heard ?? { text: "Renewals slipped in May", heard: true, failed: false });
    if (url === `${VOICE}/speak`) return json(200, w.spoken ?? { audio: "AAAA", mime: "audio/wav" });
    if (url === `${ROOM}/messages`) return json(200, w.after ?? withNorth);
    return json(404, {});
  }));
}
const open = () => render(<MemoryRouter initialEntries={[`/modules/m1_intent/sessions/${SID}/room`]}><App /></MemoryRouter>);
const box = () => screen.findByRole("textbox", { name: /Write a note in your own words/ });
const posted = (suffix: string) => calls.filter((c) => c.method === "POST" && c.url === `${VOICE}${suffix}`);

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  sessionStorage.clear();
  setSessionExpiredHandler(null);
});

describe("speech in: the person corrects the words before they are used", () => {
  test("press Speak, press stop, the words land in the box, nothing is sent until the person sends", async () => {
    mock({});
    const user = userEvent.setup();
    open();
    await user.click(await screen.findByRole("button", { name: t.mic }));
    expect(screen.getByRole("status")).toHaveTextContent(t.listening);
    expect(screen.getByRole("meter", { name: t.level })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: t.micStop }));
    await waitFor(async () => expect(await box()).toHaveValue("Renewals slipped in May"));
    const sent = posted("/transcribe")[0]?.body;
    expect(sent).toMatchObject({ mime: "audio/wav" });
    expect(typeof (sent as { audio: string }).audio).toBe("string");
    expect(calls.some((c) => c.url === `${ROOM}/messages`)).toBe(false); // heard is not sent
    await user.type(await box(), " (it was May, not April)");
    await user.click(screen.getByRole("button", { name: "Send to North" }));
    await waitFor(() => expect(calls.find((c) => c.url === `${ROOM}/messages`)?.body)
      .toMatchObject({ text: "Renewals slipped in May (it was May, not April)" }));
  });

  test("speaking again adds to the words already there", async () => {
    mock({});
    const user = userEvent.setup();
    open();
    await user.type(await box(), "First part");
    await user.click(screen.getByRole("button", { name: t.mic }));
    await user.click(screen.getByRole("button", { name: t.micStop }));
    await waitFor(async () => expect(await box()).toHaveValue("First part Renewals slipped in May"));
    expect(combineText(" a ", "")).toBe("a");
    expect(combineText("", " b ")).toBe("b");
  });

  test("nothing heard: one plain line, the box untouched", async () => {
    mock({ heard: { text: "", heard: false, failed: false } });
    const user = userEvent.setup();
    open();
    await user.click(await screen.findByRole("button", { name: t.mic }));
    await user.click(screen.getByRole("button", { name: t.micStop }));
    expect(await screen.findByText(t.noSpeech)).toBeInTheDocument();
    expect(await box()).toHaveValue("");
    expect(screen.queryByRole("alert")).toBeNull();
  });

  test.each([[{ text: "", heard: false, failed: true }], [500]])("the speech service failing is silent: %j", async (heard) => {
    mock({ heard });
    const user = userEvent.setup();
    open();
    await user.click(await screen.findByRole("button", { name: t.mic }));
    await user.click(screen.getByRole("button", { name: t.micStop }));
    expect(await screen.findByText(VOICE_DOWN)).toBeInTheDocument();
    expect(screen.queryByRole("alert")).toBeNull();
    expect(await box()).toBeEnabled(); // typing carries on
  });

  test("a microphone that cannot be used is a plain line, not an error", async () => {
    mock({});
    vi.mocked(recordWav).mockRejectedValueOnce(new Error("no-microphone"));
    const user = userEvent.setup();
    open();
    await user.click(await screen.findByRole("button", { name: t.mic }));
    expect(await screen.findByText(t.noMic)).toBeInTheDocument();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  test("the mic button works from the keyboard", async () => {
    mock({});
    const user = userEvent.setup();
    open();
    const mic = await screen.findByRole("button", { name: t.mic });
    mic.focus();
    await user.keyboard("{Enter}");
    expect(await screen.findByRole("button", { name: t.micStop })).toHaveFocus();
    await user.keyboard(" ");
    await waitFor(async () => expect(await box()).toHaveValue("Renewals slipped in May"));
  });
});

describe("speech not available", () => {
  test("a plain line, no microphone, typing works", async () => {
    mock({ voice: OFF_AIR });
    open();
    expect(await screen.findByText(VOICE_DOWN)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: t.mic })).toBeNull();
    expect(screen.queryByRole("button", { name: new RegExp(t.spoken) })).toBeNull();
    expect(await box()).toBeEnabled();
  });

  test("a voice setting that cannot be read shows nothing at all", async () => {
    mock({ voice: 404 });
    open();
    expect(await box()).toBeEnabled();
    expect(screen.queryByText(VOICE_DOWN)).toBeNull();
    expect(screen.queryByRole("button", { name: t.mic })).toBeNull();
    expect(screen.queryByRole("alert")).toBeNull();
  });
});

describe("spoken replies: play and mute", () => {
  test("the free-tier note is shown while the development provider is in use", async () => {
    mock({});
    open();
    expect(await screen.findByText(/Speech to text is on/)).toBeInTheDocument();
  });

  test("a play button on North's reply speaks that text, and the text stays on screen", async () => {
    mock({ room: withNorth });
    const user = userEvent.setup();
    open();
    await user.click(await screen.findByRole("button", { name: t.play }));
    await waitFor(() => expect(played).toEqual(["data:audio/wav;base64,AAAA"]));
    expect(posted("/speak")[0]?.body).toEqual({ text: "Who is affected?" });
    expect(screen.getByText("Who is affected?")).toBeInTheDocument();
  });

  test("speech failing while playing shows one plain sentence", async () => {
    mock({ room: withNorth, spoken: { failed: true } });
    const user = userEvent.setup();
    open();
    await user.click(await screen.findByRole("button", { name: t.play }));
    await waitFor(() => expect(posted("/speak")).toHaveLength(1));
    expect(played).toEqual([]);
    expect((await screen.findAllByText(VOICE_DOWN)).length).toBeGreaterThan(0); // one plain sentence, no vendor name
    expect(screen.queryByRole("alert")).toBeNull();
    expect(await box()).toBeEnabled(); // text keeps working
  });

  test("a new reply from North is spoken while voice is on; replies already there are not", async () => {
    mock({ room: room(), after: withNorth });
    const user = userEvent.setup();
    open();
    await user.type(await box(), "Renewals slipped");
    expect(played).toEqual([]);
    await user.click(screen.getByRole("button", { name: "Send to North" }));
    await waitFor(() => expect(played).toHaveLength(1));
    expect(posted("/speak")[0]?.body).toEqual({ text: "Who is affected?" });
  });

  test("a clipped reply shows a plain note that only the start was read", async () => {
    mock({ room: withNorth, spoken: { audio: "AAAA", mime: "audio/wav", clipped: true } });
    const user = userEvent.setup();
    open();
    expect(screen.queryByText(t.clipped)).toBeNull();
    await user.click(await screen.findByRole("button", { name: t.play }));
    expect(await screen.findByText(t.clipped)).toBeInTheDocument();
  });

  test("leaving the screen while recording discards the recording: nothing is transcribed", async () => {
    mock({});
    const user = userEvent.setup();
    const { unmount } = open();
    await user.click(await screen.findByRole("button", { name: t.mic }));
    await screen.findByRole("button", { name: t.micStop });
    const errors = vi.spyOn(console, "error");
    unmount();
    await new Promise((r) => setTimeout(r, 50));
    expect(posted("/transcribe")).toHaveLength(0);
    expect(errors).not.toHaveBeenCalled();
  });

  test("mute is remembered on the server, stops spoken replies and hides the play buttons", async () => {
    mock({ room: room(), after: withNorth });
    const user = userEvent.setup();
    open();
    const toggle = await screen.findByRole("button", { name: `${t.spoken}: ${t.on}` });
    expect(toggle).toHaveAttribute("aria-pressed", "true");
    await user.click(toggle);
    expect(await screen.findByRole("button", { name: `${t.spoken}: ${t.off}` })).toHaveAttribute("aria-pressed", "false");
    expect(posted("")[0]?.body).toEqual({ on: false });
    await user.type(await box(), "Renewals slipped");
    await user.click(screen.getByRole("button", { name: "Send to North" }));
    expect(await screen.findByText("Who is affected?")).toBeInTheDocument(); // the text is always shown
    expect(screen.queryByRole("button", { name: t.play })).toBeNull();
    expect(posted("/speak")).toHaveLength(0);
    expect(played).toEqual([]);
  });

  test("a voice that was muted before opens muted", async () => {
    mock({ voice: { ...ON, on: false }, room: withNorth });
    open();
    expect(await screen.findByRole("button", { name: `${t.spoken}: ${t.off}` })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: t.play })).toBeNull();
  });
});
