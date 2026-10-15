// M1-P06: typed calls for speech (M1-08 speech in, M1-09 spoken replies). Audio travels as base64 inside the JSON so
// the one shared client stays the only caller of fetch; it exists in memory for one request and is never saved.
import { apiGet, apiSend } from "../../../api/client";
import { sessionPath } from "../api";

const base = (sessionId: string) => `${sessionPath(sessionId)}/voice`;

export interface Voice {
  /** False when no speech provider is set up (or it is switched off): the screens use typing only. */
  available: boolean;
  /** This person's own switch for spoken replies, remembered on the server per seat. */
  on: boolean;
  /** Plain words for the person when speech is not available. */
  message: string | null;
  /** Shown while the development speech provider is in use. */
  note: string | null;
  max_seconds: number;
}
export interface Heard {
  text: string;
  heard: boolean;
  /** The speech service did not answer; the person carries on by typing, with no error shown. */
  failed: boolean;
}
export type Spoken = { audio: string; mime: string; clipped?: boolean } | { failed: true };

export const getVoice = (sessionId: string) => apiGet<Voice>(base(sessionId));
export const setVoiceOn = (sessionId: string, on: boolean) => apiSend<Voice>("POST", base(sessionId), { on });
export const transcribe = (sessionId: string, audio: string, mime: string) =>
  apiSend<Heard>("POST", `${base(sessionId)}/transcribe`, { audio, mime });
export const speak = (sessionId: string, text: string) => apiSend<Spoken>("POST", `${base(sessionId)}/speak`, { text });
