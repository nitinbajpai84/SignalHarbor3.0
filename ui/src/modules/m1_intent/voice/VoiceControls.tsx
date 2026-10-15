import { useEffect, useRef, useState } from "react";

import Icon from "../../../components/Icon";
import { m1Voice as t } from "../copy";
import { recordWav } from "./recorder";
import { getVoice, setVoiceOn, speak, transcribe, type Voice } from "./voiceApi";

// M1-P06: the microphone, the spoken-replies switch and the play button for the private room. Speech never shows an
// error: when it cannot be used the person is told in one plain line and carries on by typing.

/** The person's voice setting for this session; null while loading or when it cannot be read (then nothing is shown). */
export function useVoice(sessionId: string) {
  const [voice, setVoice] = useState<Voice | null>(null);
  useEffect(() => {
    if (sessionId === "") return; // M1-UI2: a draft that is not saved yet has no session to ask
    let live = true;
    getVoice(sessionId).then(
      (v) => live && setVoice(v),
      () => undefined,
    );
    return () => {
      live = false;
    };
  }, [sessionId]);
  const setOn = (on: boolean) => setVoiceOn(sessionId, on).then(setVoice, () => undefined);
  return { voice, setOn };
}

/** Joins words already in the box with newly spoken ones, so speaking again adds to the text instead of replacing it. */
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

/** The one sentence shown whenever North's voice cannot be used (speaking or listening); text keeps working. */
export const VOICE_DOWN = "North's voice is not available right now; keep typing.";
const CLIPPED = "m1-voice-clipped";
const DOWN = "m1-voice-down"; // detail true: a spoken reply failed (the bar shows VOICE_DOWN); false: one played, clear it
const tell = (name: string, detail: boolean) => window.dispatchEvent(new CustomEvent(name, { detail }));
let playing: HTMLAudioElement | null = null;
/** Speaks one reply and says whether it started. Any trouble (no audio, the service failing, the browser refusing to play) shows the one plain sentence, never an error. */
export async function playReply(sessionId: string, text: string): Promise<boolean> {
  try {
    const got = await speak(sessionId, text);
    if (!("audio" in got)) {
      tell(DOWN, true);
      return false;
    }
    tell(CLIPPED, got.clipped === true); // the bar shows the small note
    playing?.pause();
    playing = new Audio(`data:${got.mime};base64,${got.audio}`);
    await playing.play();
    tell(DOWN, false);
    return true;
  } catch {
    tell(DOWN, true); // the text is on screen; the bar says the voice is down
    return false;
  }
}

type MicState = "idle" | "listening" | "working";
type MicNote = "noSpeech" | "noMic" | "unavailable" | null;

export function VoiceBar({ sessionId, voice, onSwitch, onText, disabled, bare = false }: {
  sessionId: string;
  voice: Voice | null;
  onSwitch: (on: boolean) => void;
  /** M1-UI2: the microphone alone (Nira's panel has its own spoken-replies switch in its head). */
  bare?: boolean;
  onText: (text: string) => void;
  disabled: boolean;
}) {
  const [mic, setMic] = useState<MicState>("idle");
  const [note, setNote] = useState<MicNote>(null);
  const [level, setLevel] = useState(0);
  const [clipped, setClipped] = useState(false);
  const stopper = useRef<AbortController | null>(null);
  const gone = useRef(false);
  useEffect(() => {
    gone.current = false;
    const on = (e: Event) => setClipped((e as CustomEvent<boolean>).detail);
    const down = (e: Event) => setNote((e as CustomEvent<boolean>).detail ? "unavailable" : null);
    window.addEventListener(CLIPPED, on);
    window.addEventListener(DOWN, down);
    return () => {
      gone.current = true; // leaving the screen: stop and throw the recording away
      stopper.current?.abort();
      window.removeEventListener(CLIPPED, on);
      window.removeEventListener(DOWN, down);
    };
  }, []);
  if (!voice) return null;
  if (!voice.available) return <p className="n-muted">{VOICE_DOWN}</p>;

  async function press() {
    if (mic === "listening") {
      stopper.current?.abort(); // the recording then finishes below
      return;
    }
    setNote(null);
    const stop = new AbortController();
    stopper.current = stop;
    setMic("listening");
    let wav: Blob;
    try {
      wav = await recordWav({ signal: stop.signal, maxMs: (voice?.max_seconds ?? 60) * 1000, onLevel: setLevel });
    } catch {
      if (gone.current) return;
      setMic("idle");
      setNote("noMic");
      return;
    }
    if (gone.current) return; // the screen closed while recording: nothing is sent
    setLevel(0);
    setMic("working");
    try {
      const heard = await transcribe(sessionId, await toBase64(wav), "audio/wav");
      if (gone.current) return;
      if (heard.failed) setNote("unavailable");
      else if (!heard.heard) setNote("noSpeech");
      else onText(heard.text);
    } catch {
      if (gone.current) return;
      setNote("unavailable");
    }
    setMic("idle");
  }

  return (
    <div>
      <div className="m1-actions">
        <button type="button" className="n-btn" onClick={() => void press()} disabled={disabled || mic === "working"} aria-label={bare ? (mic === "listening" ? t.micStopNira : t.micNira) : undefined}>
          {bare ? <Icon name="mic" size={13} /> : null}
          {mic === "listening" ? t.micStop : t.mic}
        </button>
        {bare ? null : (
          <button type="button" className="n-btn" aria-pressed={voice.on} onClick={() => onSwitch(!voice.on)}>
            {t.spoken}: {voice.on ? t.on : t.off}
          </button>
        )}
        {mic === "listening" ? <meter min={0} max={1} value={level} aria-label={t.level} /> : null}
      </div>
      {bare && mic === "idle" && !note ? null : (
        <p className="n-muted" role={bare ? undefined : "status"}>
          {mic === "listening" ? t.listening : mic === "working" ? t.working : note === "unavailable" ? VOICE_DOWN : note ? t[note] : t.micHelp}
        </p>
      )}
      {voice.note && !bare ? <p className="n-muted">{voice.note}</p> : null}
      {clipped && !bare ? <p className="n-muted">{t.clipped}</p> : null}
    </div>
  );
}

/** A play button for one of North's replies; shown only while speech is available and this person has it switched on. */
export function PlayButton({ sessionId, voice, text }: { sessionId: string; voice: Voice | null; text: string }) {
  if (!voice?.available || !voice.on) return null;
  return (
    <button type="button" className="n-btn" onClick={() => void playReply(sessionId, text)}>
      {t.play}
    </button>
  );
}

/** Speaks each new answer from North while spoken replies are on. Replies already there when the room opened stay quiet. */
export function useAutoSpeak(
  sessionId: string,
  voice: Voice | null,
  turns: { id: string; role: string; text: string; answered?: boolean }[],
) {
  const last = turns[turns.length - 1];
  const seen = useRef<string | undefined>(last?.id);
  useEffect(() => {
    if (!last || last.id === seen.current) return;
    seen.current = last.id;
    if (voice?.available && voice.on && last.role === "north" && last.answered !== false) void playReply(sessionId, last.text);
  }, [last?.id]);
}
