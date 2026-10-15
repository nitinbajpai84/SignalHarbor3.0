import { useEffect, useRef, useState, useSyncExternalStore, type DragEvent, type RefObject } from "react";

import { apiGet, apiSend } from "../../api/client";
import Icon from "../../components/Icon";
import { Button, Chip } from "../../design";
import { recordWav } from "../../modules/m1_intent/voice/recorder";

// V1 Voice: type, talk or upload with every agent (North, Span, Span, Lumen). One composer (text box, microphone (files are added through "Add context", or dropped on the box),
// Send), a play button for an agent's message and a "Read replies aloud" switch. Speech never shows an error: when it cannot be
// used the screen says so in one line and carries on in text. Calls sh_platform/v1/v1_voice_routes.py. Copied from 2.0's
// modules/m1_intent/voice/VoiceControls.tsx (playReply, the recording flow, combineText, toBase64) and its recorder.

export const NOT_AVAILABLE = "Voice is not available right now; keep typing.";
const NO_SPEECH = "We did not hear anything. Please try again, or type.";
const NO_MIC = "We could not use your microphone. You can type instead.";
const MAX_MS = 120_000; // 2.0's max_recording_seconds
const NAME_ONLY = /\.(png|jpe?g|gif|webp|bmp|tiff?|heic|pdf)$/i; // read by name only for now

interface Status { available: boolean; note: string | null }
type Spoken = { audio: string; mime: string; clipped?: boolean } | { failed: true; note?: string };

// ---- the person's two switches, remembered in this browser (localStorage, guarded) --------------------------------------------
const KEYS = { read: "sh-v1-read-aloud", auto: "sh-v1-send-after-speaking" } as const;
type Prefs = Record<keyof typeof KEYS, boolean>;
const stored = (k: keyof typeof KEYS) => {
  try { return localStorage.getItem(KEYS[k]) === "1"; } catch { return false; }
};
let prefs: Prefs = { read: stored("read"), auto: stored("auto") };
const subs = new Set<() => void>();
function setPref(k: keyof typeof KEYS, on: boolean) {
  prefs = { ...prefs, [k]: on };
  try { localStorage.setItem(KEYS[k], on ? "1" : "0"); } catch { /* the switch still works for this visit */ }
  subs.forEach((f) => f());
}
const subscribe = (f: () => void) => { subs.add(f); return () => { subs.delete(f); }; };
const usePrefs = () => useSyncExternalStore(subscribe, () => prefs);

// ---- is voice on: asked once per page load ----------------------------------------------------------------------------------
let asked: Promise<Status> | null = null;
/** For tests: ask the server again. */
export const forgetVoice = () => { asked = null; };

/** Whether voice can be used (null while asking), the note, and the person's two switches. */
export function useVoice() {
  const [status, setStatus] = useState<Status | null>(null);
  const p = usePrefs();
  useEffect(() => {
    let live = true;
    asked ??= apiGet<Status>("/api/v1/voice").then(
      (s) => ({ available: s?.available === true, note: s?.available === true ? s.note ?? null : s?.note || NOT_AVAILABLE }),
      () => ({ available: false, note: NOT_AVAILABLE }));
    void asked.then((s) => { if (live) setStatus(s); });
    return () => { live = false; };
  }, []);
  return {
    available: status ? status.available : null, note: status?.note ?? null,
    readAloud: p.read, setReadAloud: (on: boolean) => setPref("read", on),
    autoSend: p.auto, setAutoSend: (on: boolean) => setPref("auto", on),
  };
}

/** Joins words already in the box with newly spoken ones (2.0's combineText). */
export function combineText(base: string, addition: string): string {
  const [b, a] = [base.trim(), addition.trim()];
  return b && a ? `${b} ${a}` : b || a;
}

async function toBase64(blob: Blob): Promise<string> {
  const bytes = new Uint8Array(await blob.arrayBuffer());
  let binary = "";
  for (let i = 0; i < bytes.length; i += 0x8000) binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return btoa(binary);
}

let playing: HTMLAudioElement | null = null;
let downNote = NOT_AVAILABLE; // why the last read-aloud failed: the server's words when a model account is in trouble
/** Reads one message aloud; false (never an error) when it could not. */
export async function playText(text: string): Promise<boolean> {
  try {
    const got = await apiSend<Spoken>("POST", "/api/v1/voice/speak", { text });
    if (!("audio" in got)) { downNote = got.note || NOT_AVAILABLE; return false; }
    playing?.pause();
    playing = new Audio(`data:${got.mime};base64,${got.audio}`);
    await playing.play();
    return true;
  } catch {
    return false;
  }
}

// ---- the microphone ---------------------------------------------------------------------------------------------------------
type Mic = "idle" | "listening" | "working";

/** Click to start and click to stop, or hold and release. The words go to `onText`; the person reads them before sending. */
export function MicButton({ onText, disabled, agent = "the agent" }: { onText: (text: string) => void; disabled?: boolean; agent?: string }) {
  const { available, note: why } = useVoice();
  const [mic, setMic] = useState<Mic>("idle");
  const [note, setNote] = useState("");
  const [level, setLevel] = useState(0);
  const stopper = useRef<AbortController | null>(null);
  const gone = useRef(false);
  const press = useRef({ pointer: false, at: 0 });
  useEffect(() => {
    gone.current = false;
    return () => { gone.current = true; stopper.current?.abort(); };
  }, []);
  if (available === null) return null;
  if (!available) {
    return (
      <>
        <button type="button" className="ds-btn" disabled aria-label={`Speak to ${agent}`} title={why || NOT_AVAILABLE}><Icon name="mic" size={14} /></button>
        {why && why !== NOT_AVAILABLE ? <span className="ds-muted" role="status">{why}</span> : null}
      </>
    );
  }

  const stop = () => stopper.current?.abort();
  async function start() {
    setNote("");
    const ctl = new AbortController();
    stopper.current = ctl;
    setMic("listening");
    let wav: Blob;
    try {
      wav = await recordWav({ signal: ctl.signal, maxMs: MAX_MS, onLevel: setLevel });
    } catch {
      if (!gone.current) { setMic("idle"); setNote(NO_MIC); }
      return;
    }
    if (gone.current) return; // the screen closed while recording: nothing is sent
    setLevel(0);
    setMic("working");
    try {
      const heard = await apiSend<{ text?: string; failed?: boolean; note?: string }>("POST", "/api/v1/voice/transcribe",
        { audio: await toBase64(wav), mime: "audio/wav" });
      if (gone.current) return;
      if (heard.failed) setNote(heard.note || NOT_AVAILABLE);
      else if (!heard.text) setNote(NO_SPEECH);
      else onText(heard.text);
    } catch {
      if (!gone.current) setNote(NOT_AVAILABLE);
    }
    if (!gone.current) setMic("idle");
  }

  return (
    <>
      <button type="button" className="ds-btn" disabled={disabled || mic === "working"} aria-pressed={mic === "listening"}
        aria-label={mic === "listening" ? "Stop and write it down" : `Speak to ${agent}`}
        title="Click to speak and click again to stop, or hold and release"
        onPointerDown={() => { if (mic === "idle") { press.current = { pointer: true, at: Date.now() }; void start(); } }}
        onPointerUp={() => { if (press.current.pointer && Date.now() - press.current.at > 400) stop(); }}
        onClick={() => {
          if (press.current.pointer) { press.current.pointer = false; return; } // this press already started (or stopped) it
          if (mic === "listening") stop();
          else if (mic === "idle") void start();
        }}>
        <Icon name="mic" size={14} />{mic === "listening" ? " Stop" : null}
      </button>
      {mic === "listening" ? <meter min={0} max={1} value={level} aria-label="Microphone volume" style={{ width: 48 }} /> : null}
      {mic === "working" ? <span className="ds-muted" role="status">Writing it down…</span> : note ? <span className="ds-muted">{note}</span> : null}
    </>
  );
}

// ---- reading aloud ----------------------------------------------------------------------------------------------------------

/** A small play button on one agent message. Shown only while voice is available. */
export function SpeakButton({ text }: { text: string }) {
  const { available } = useVoice();
  const [down, setDown] = useState(false);
  if (!available) return null;
  return (
    <span>
      <button type="button" className="ds-link" aria-label="Read this aloud" title="Read this aloud"
        onClick={() => void playText(text).then((ok) => setDown(!ok))}><Icon name="speaker" size={14} /></button>
      {down ? <span className="ds-muted"> {downNote}</span> : null}
    </span>
  );
}

/** The person's "Read replies aloud" switch, remembered in this browser. */
export function ReadAloudToggle() {
  const { available, readAloud, setReadAloud } = useVoice();
  if (!available) return null;
  return (
    <label style={{ display: "inline-flex", gap: 4, alignItems: "center" }}>
      <input type="checkbox" checked={readAloud} onChange={(e) => setReadAloud(e.target.checked)} /> Read replies aloud
    </label>
  );
}

/** Reads each new agent reply aloud while the switch is on. Replies already on screen when it opened stay quiet. */
export function useReadAloud(last: { id: string; text: string } | null | undefined) {
  const { available, readAloud } = useVoice();
  const seen = useRef<string | undefined>(undefined);
  const started = useRef(false);
  useEffect(() => {
    if (!last) return;
    if (!started.current) { started.current = true; seen.current = last.id; return; }
    if (last.id === seen.current) return;
    seen.current = last.id;
    if (available && readAloud) void playText(last.text);
  }, [last?.id]); // eslint-disable-line react-hooks/exhaustive-deps
}

// ---- the composer: type, talk or upload -------------------------------------------------------------------------------------

/** Props to spread on any element (the whole conversation pane, a Context box) so files dropped on it join the message. */
export const dropFiles = (add: (files: File[]) => void) => ({
  onDragOver: (e: DragEvent) => e.preventDefault(),
  onDrop: (e: DragEvent) => { e.preventDefault(); add(Array.from(e.dataTransfer.files)); },
});

export function Composer({ agent, text, setText, files, setFiles, onSend, onEmpty, busy, disabled, placeholder, error, boxRef }: {
  agent: string;
  text: string;
  setText: (t: string) => void;
  files: File[];
  setFiles: (f: File[]) => void;
  /** The words and the files the agent can read; pictures and PDFs go by name only, in the words. */
  onSend: (text: string, files: File[]) => void;
  /** When given, Send is always active and an empty send calls this (the page says what to type) instead of being greyed out. */
  onEmpty?: () => void;
  busy?: boolean;
  disabled?: boolean;
  placeholder?: string;
  error?: string;
  boxRef?: RefObject<HTMLTextAreaElement | null>;
}) {
  const { available, note, autoSend, setAutoSend } = useVoice();
  const nameOnly = files.filter((f) => NAME_ONLY.test(f.name));
  const send = (said: string) => {
    const readable = files.filter((f) => !NAME_ONLY.test(f.name));
    const words = combineText(said, nameOnly.length ? `I added ${nameOnly.map((f) => f.name).join(", ")}.` : "");
    if (busy || disabled) return;
    if (!words && !readable.length) { onEmpty?.(); return; }
    onSend(words, readable);
  };
  const spoken = (said: string) => {
    const next = combineText(text, said);
    setText(next);
    if (autoSend) send(next);
  };
  return (
    <form onSubmit={(e) => { e.preventDefault(); send(text.trim()); }} aria-label={`Message ${agent}`}
      {...dropFiles((add) => setFiles([...files, ...add]))} style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      {files.length ? (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
          {files.map((f, i) => <Chip key={`${f.name}-${i}`} onClick={() => setFiles(files.filter((_, j) => j !== i))}>{f.name} ×</Chip>)}
        </div>
      ) : null}
      {nameOnly.length ? (
        <p className="ds-muted" style={{ margin: 0 }}>
          {agent} can&apos;t read this type yet ({nameOnly.map((f) => f.name).join(", ")}); paste the text. Only the name is sent.
        </p>
      ) : null}
      {error ? <p role="alert" style={{ margin: 0 }}>{error}</p> : null}
      <div style={{ display: "flex", gap: 8, alignItems: "flex-end", flexWrap: "wrap" }}>
        <textarea ref={boxRef} aria-label="Your message" rows={2} value={text} onChange={(e) => setText(e.target.value)} disabled={disabled}
          style={{ flex: "1 1 200px", minWidth: 0, background: "var(--ds-ground)", color: "var(--ds-ink)", border: "1px solid var(--ds-line-2)", borderRadius: 8, padding: "8px 10px", font: "inherit" }} placeholder={placeholder ?? `Write or speak to ${agent}`}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); e.currentTarget.form?.requestSubmit(); } }} />
        <MicButton onText={spoken} disabled={disabled || busy} agent={agent} />
        <Button type="submit" variant="primary" disabled={busy || disabled || (!onEmpty && !text.trim() && files.length === 0)}>Send</Button>
      </div>
      {available === false ? <p className="ds-muted" style={{ margin: 0 }}>{NOT_AVAILABLE}</p> : available ? (
        <div className="ds-muted" style={{ display: "flex", gap: 16, flexWrap: "wrap", fontSize: 13 }}>
          <ReadAloudToggle />
          <label style={{ display: "inline-flex", gap: 4, alignItems: "center" }}>
            <input type="checkbox" checked={autoSend} onChange={(e) => setAutoSend(e.target.checked)} /> Send automatically after speaking
          </label>
          {note ? <span>{note}</span> : null}
        </div>
      ) : null}
    </form>
  );
}
