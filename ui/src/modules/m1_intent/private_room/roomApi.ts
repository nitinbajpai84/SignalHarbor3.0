// M1-P04: typed calls for the private room. Everything goes through the shared client (token-aware: see ../api.ts).
import { apiGet } from "../../../api/client";
import { pGet, pSend, sessionPath } from "../api";

const base = (sessionId: string) => `${sessionPath(sessionId)}/room`;

export type Priority = "must" | "should" | "could" | "not_this_time";
export const PRIORITIES: Priority[] = ["must", "should", "could", "not_this_time"];

export interface PracticeCard {
  problem_id: string;
  label: string;
  company_decides: string;
  items: string[];
  decision: "offered" | "added" | "dismissed";
  decided_at?: string;
}
/** The four kinds of note: what we intend to do now, what hurts today, what to watch in future, a lever we change. */
export type NoteKind = "intent" | "pain_point" | "future_signal" | "lever";
/** M1-11: one field of the note form, from the contract file. `kinds` lists the kinds of note it applies to; empty: all. */
export interface FormField {
  id: string;
  label: string;
  kind: "text" | "number" | "labels";
  ask: string;
  required: boolean;
  person_only: boolean;
  guess: boolean;
  kinds?: NoteKind[];
}
/** One kind of note as the form offers it: its plain label, the heading it has on the board and charter, and its own details. */
export interface KindInfo {
  id: NoteKind;
  label: string;
  heading: string;
  ask: string;
  fields: FormField[];
}
export type FieldValue = string | number | string[];
export interface RoomNote {
  id: string;
  text: string;
  state: string;
  /** Where the note came from: typed, the library, the person's one interview or North's cards from the conversation. */
  source: { kind: "typed" | "library" | "interview" | "north"; problem_id?: string; q?: string; from?: string };
  /** False on a draft North wrote: it goes to the board only after the person keeps, changes or marks it anonymous. */
  confirmed?: boolean | null;
  priority: Priority | null;
  practice: PracticeCard | null;
  practice_added: string[];
  created_at: string;
  updated_at: string;
  /** M1-11: the form fields the person (or North, as a suggestion) filled; labels here are the confirmed ones. */
  fields: Record<string, FieldValue>;
  labels_suggested: string[];
  /** M1-12: true when this note will be posted without a name. */
  anonymous: boolean;
  /** True when the person sealed it: the wall and the board show it as a sealed card to anyone not on the area's list. */
  restricted?: boolean;
  /** What kind of note this is; one saved before kinds existed is an intent. */
  kind?: NoteKind;
  /** North's suggestion for the kind: shown as a suggestion, the person decides. */
  kind_suggested?: NoteKind | null;
  /** Ids of the form fields still empty. */
  missing: string[];
}
export interface RoomTurn {
  id: string;
  role: "person" | "north";
  text: string;
  at: string;
  /** False when North could not answer; the text is then a plain message from the system. */
  answered?: boolean;
  readback?: { note_id: string; text: string };
}
export interface Room {
  open: boolean;
  message: string | null;
  /** M1-P05: the session's own clear title. */
  title: string;
  turns: RoomTurn[];
  notes: RoomNote[];
  form: FormField[];
  kinds?: KindInfo[];
  /** The organiser's rule for names on notes: open ("named"), never ("anonymous") or each person's choice ("choice"). */
  names?: "named" | "choice" | "anonymous";
  /** Saved but unsent notes: what the end of the rooms would send for this person (named = would go under their name). */
  unsent?: { count: number; named: number; message: string | null };
  /** LI-M1: drafts that came from the person's interview, and the kinds of note they have none of yet (North asks about those). */
  interview?: { drafted: boolean; gaps: { kind: NoteKind; ask: string }[] };
  /** Set when North's cards could not be written: the reason in plain words. */
  cards_message?: string;
  north: {
    practice_on: boolean;
    library_on: boolean;
    available: boolean;
    /** What others in the industry usually raise for each kind of note, from the company's pack; empty with no pack. */
    suggestions?: Partial<Record<NoteKind, string[]>>;
    suggestions_label?: string | null;
    suggestions_empty?: string | null;
  };
}
export interface LibraryProblem {
  id: string;
  text: string;
}
export interface Library {
  on: boolean;
  /** False when the company's industry has no problem library at all (then `message` says so). */
  available: boolean;
  label: string;
  problems: LibraryProblem[];
  message: string | null;
}
export type MessageKind = "note" | "answer" | "correction";

export const getRoom = (sessionId: string) => pGet<Room>(sessionId, base(sessionId));
export const getLibrary = (sessionId: string) => pGet<Library>(sessionId, `${base(sessionId)}/library`);
// askHowOthers: the person pressed "Ask North how others do it"; otherwise North listens and checks (deck slide 3)
export const sendMessage = (sessionId: string, text: string, kind: MessageKind, noteId?: string, askHowOthers = false) =>
  pSend<Room>(sessionId, `${base(sessionId)}/messages`, {
    text, kind, ...(noteId ? { note_id: noteId } : {}), ...(askHowOthers ? { ask_how_others: true } : {}),
  });
export const startFromLibrary = (sessionId: string, problemId: string, text: string, priority: Priority | null) =>
  pSend<Room>(sessionId, `${base(sessionId)}/notes`, { from_library: problemId, text, priority });
const notePath = (sessionId: string, noteId: string) => `${base(sessionId)}/notes/${encodeURIComponent(noteId)}`;
export const setPriority = (sessionId: string, noteId: string, priority: Priority | null) =>
  pSend<Room>(sessionId, notePath(sessionId, noteId), { priority });
export const decidePractice = (sessionId: string, noteId: string, action: "add" | "dismiss") =>
  pSend<Room>(sessionId, `${notePath(sessionId, noteId)}/practice`, { action });
/** M1-11, M1-12: save the form fields and the By name / Anonymous choice of a draft. A cleared field is null. */
export const saveNote = (
  sessionId: string,
  noteId: string,
  change: { fields?: Record<string, FieldValue | null>; anonymous?: boolean; restricted?: boolean; kind?: NoteKind; keep?: boolean },
) => pSend<Room>(sessionId, notePath(sessionId, noteId), change);
export const prefillNote = (sessionId: string, noteId: string) =>
  pSend<Room>(sessionId, `${notePath(sessionId, noteId)}/prefill`);
export const submitNote = (sessionId: string, noteId: string) =>
  pSend<Room>(sessionId, `${notePath(sessionId, noteId)}/submit`);

/** LI-M1: North turns the conversation into note cards, which wait in the room for the person to keep, change or mark anonymous. */
export const writeCards = (sessionId: string) => pSend<Room>(sessionId, `${base(sessionId)}/notes`, { from_conversation: true });
/** IC-2e: pick up a suggestion card from the wall, turning it into a note card. */
export const pickUpSuggestion = (sessionId: string, suggestionId: string) =>
  pSend<Room>(sessionId, `${base(sessionId)}/notes`, { from_suggestion: suggestionId });
