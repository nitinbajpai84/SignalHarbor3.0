// Typed calls for module 1. Everything goes through the shared client; nothing here calls fetch.
import { apiGet, apiSend, guestBlob, guestGet, guestSend } from "../../api/client";
import { loadToken } from "./room/guestToken";

const BASE = "/api/modules/m1_intent";

// M1-P05: a person who joined by link has no account: their token (kept in this tab) goes in the header of every
// participant call for THEIR session. A signed-in person has none and the cookie is used.
const tokenFor = (sessionId: string) => {
  return loadToken(sessionId)?.token;
};
export const pGet = <T>(sessionId: string, path: string) => guestGet<T>(path, tokenFor(sessionId));
export const pSend = <T>(sessionId: string, path: string, body?: unknown) =>
  guestSend<T>("POST", path, body, tokenFor(sessionId));

export interface Split {
  briefing: number;
  individual: number;
  together: number;
}
/** How names show on notes: the organiser decides in Prepare. A session saved before this had none: "choice". */
export type NamesRule = "named" | "choice" | "anonymous";
export interface Preparation {
  purpose: string;
  outcome: string;
  charter_template: string;
  seats: number;
  length_minutes: number;
  split: Split;
  north_industry_practice: boolean;
  north_problem_library: boolean;
  briefing_video: string;
  approver_name: string;
  approver_account_id: string | null;
  names?: NamesRule;
  /** How many people must sign: one (the default, null) or two. */
  signers?: 1 | 2 | null;
  /** How many working days the wall stays open: 1-20 or null for default. */
  wall_window_days?: number | null;
  /** The wall's topic or department (1 to 60 characters), or none. */
  topic?: string | null;
}
export interface SessionView {
  /** The session's plain name, when the route serves it. */
  label?: string;
  id: string;
  state: string;
  paused_from: string | null;
  is_solo: boolean;
  editable: boolean;
  preparation: Preparation;
  outcome_id: string;
  created_at: string;
  updated_at: string;
  /** Small counters of what people did and typed in this session: numbers only, never the content. */
  inputs?: { actions: number; free_text: number };
}
export interface SessionRow {
  id: string;
  state: string;
  label: string;
  seats: number;
  topic?: string | null;
  outcome_id: string;
  updated_at: string;
}
/** One wall of the company: numbers only. */
export interface Wall {
  id: string;
  topic: string | null;
  purpose: string;
  state: string;
  cards_count: number;
  people_count: number;
}
export const listWalls = () => apiGet<{ walls: Wall[] }>(`${BASE}/walls`);
export interface TemplateRow {
  id: string;
  name: string;
  preparation: Preparation;
  created_at: string;
}
export interface CharterTemplate {
  id: string;
  name: string;
  description: string;
}
export interface North {
  problem_library_available: boolean;
  industry_practice_available: boolean;
  problem_count: number;
  message: string | null;
}
/** One value Prepare was drafted with, and the plain label of where it came from. */
export interface DraftedValue<T> {
  value: T;
  source: string;
}
/** LI-M1: the session drafted from the company profile. `available` is false when the profile holds nothing to draft from. */
export interface ProfileDraft {
  available: boolean;
  fields: {
    purpose?: DraftedValue<string>;
    outcome?: DraftedValue<string>;
    seats?: DraftedValue<number>;
    approver_name?: DraftedValue<string>;
    names?: DraftedValue<NamesRule>;
    length_minutes?: DraftedValue<number>;
  };
  people: { name: string; role: string; source: string }[];
}
export interface Lists {
  seats: { min: number; max: number };
  time_presets_minutes: number[];
  custom_length_minutes: { min: number; max: number };
  min_stage_minutes: number;
  default_length_minutes: number;
  default_split: Split;
  default_split_percent: Split;
  briefing_video_options: string[];
  charter_templates: CharterTemplate[];
  default_template: string;
  north: North;
  profile_draft?: ProfileDraft;
}

export const getLists = () => apiGet<Lists>(`${BASE}/lists`);
export const listSessions = () => apiGet<SessionRow[]>(`${BASE}/sessions`);
export const getSession = (id: string) => apiGet<SessionView>(`${BASE}/sessions/${encodeURIComponent(id)}`);
export const createDraft = (p: Preparation, drafted = false) =>
  apiSend<SessionView>("POST", `${BASE}/sessions`, drafted ? { ...p, drafted: true } : p);
export const updateDraft = (id: string, p: Preparation) =>
  apiSend<SessionView>("PUT", `${BASE}/sessions/${encodeURIComponent(id)}`, p);
export const deleteDraft = (id: string) =>
  apiSend<{ deleted: boolean }>("DELETE", `${BASE}/sessions/${encodeURIComponent(id)}?confirm=yes`);
export const listTemplates = () => apiGet<TemplateRow[]>(`${BASE}/templates`);
export const saveTemplate = (name: string, sessionId: string) =>
  apiSend<TemplateRow>("POST", `${BASE}/templates`, { name, session_id: sessionId });

// M1-P03 briefing, Nira and the stage timer (M1-05, M1-06, M1-07, M1-14).
export interface Rule {
  id: string;
  label: string;
  text: string;
}
export interface BriefingView {
  stage: string;
  company_name: string;
  title: string;
  rules: Rule[];
  video: { mode: "file"; content_type: string } | { mode: "placeholder" } | { mode: "none" };
  read_aloud: { available: boolean; message?: string };
  me: { role: "organiser" | "participant"; status: "waiting" | "clear" | "asked" };
  can_send: boolean;
  /** "briefing" until this person is clear (a latecomer sees it before their room), then "room". */
  next: "briefing" | "room";
  /** Organiser only. */
  confirmed?: number;
  seats?: number;
}
export interface NiraReply {
  available: boolean;
  name: string;
  role: string;
  text: string;
}
export type NiraKind = "welcome" | "ask" | "now" | "warning";
export interface TimerExtension {
  at: string;
  minutes: number;
}
export type TimerView =
  | { stage: string; timed: false; now: string }
  | {
      stage: string;
      timed: true;
      status: "running" | "warning" | "over";
      started_at: string;
      ends_at: string;
      now: string;
      remaining_seconds: number;
      warning_seconds: number;
      extensions: TimerExtension[];
      extension_minutes: number[];
      may_extend: boolean;
    };

export const sessionPath = (id: string) => `${BASE}/sessions/${encodeURIComponent(id)}`;
export const getBriefing = (id: string) => pGet<BriefingView>(id, `${sessionPath(id)}/briefing`);
export const confirmClear = (id: string) => pSend<BriefingView>(id, `${sessionPath(id)}/briefing/confirm`, { answer: "clear" });
export const sendEveryone = (id: string) => apiSend<{ state: string }>("POST", `${sessionPath(id)}/briefing/send`);
/** The briefing video as a Blob: a <video src> cannot send a guest's token, so it is fetched with the token header. */
export const getBriefingVideo = (id: string) => guestBlob(`${sessionPath(id)}/briefing/video`, tokenFor(id));
export const askNira = (id: string, kind: NiraKind, question?: string) =>
  pSend<NiraReply>(id, `${sessionPath(id)}/nira`, question === undefined ? { kind } : { kind, question });
export const getTimer = (id: string) => pGet<TimerView>(id, `${sessionPath(id)}/timer`);
export const extendTimer = (id: string, minutes: number) =>
  apiSend<TimerView>("POST", `${sessionPath(id)}/timer/extend`, { minutes });
// ---- M1-P02: the room, the join link and the lobby ----------------------------------------------------------------

export type SeatState = "free" | "taken" | "revoked";
export interface Seat {
  n: number;
  state: SeatState;
  mine: boolean;
  name?: string;
  role?: string;
  /** Only the organiser is told who came late. */
  late?: boolean;
}
export interface SeatMe {
  seat: number;
  name: string;
  role: string;
  late: boolean;
  see_briefing_first: boolean;
}
/** What the lobby shows one viewer: the stage, the seat picture and, for a seated person, their own seat. */
export interface RoomView {
  session_id: string;
  state: string;
  length_minutes: number;
  is_solo: boolean;
  organiser: boolean;
  me: SeatMe | null;
  seats: Seat[];
  arrived: number;
  seat_count: number;
}
/** The answer to opening the link: the free seats, or the person's own seat when they are already seated. */
export interface JoinView {
  session_id: string;
  state: string;
  signed_in: boolean;
  length_minutes: number;
  /** Given once, when a person with no account takes a seat. Kept in this browser tab only. */
  token: string | null;
  me: SeatMe | null;
  seats: { n: number; state: SeatState }[];
}
export interface LinkView {
  join_path: string;
  state: string;
}

const roomPath = (sessionId: string) => `${BASE}/sessions/${encodeURIComponent(sessionId)}`;
export const startRoom = (sessionId: string) => apiSend<LinkView>("POST", `${roomPath(sessionId)}/start`);
export const newJoinLink = (sessionId: string) => apiSend<LinkView>("POST", `${roomPath(sessionId)}/link`);
export const getJoinLink = (sessionId: string) => apiGet<LinkView>(`${roomPath(sessionId)}/join-link`);
export const revokeSeat = (sessionId: string, seat: number, reopen = false) =>
  apiSend<RoomView>("POST", `${roomPath(sessionId)}/seats/${seat}/revoke${reopen ? "?reopen=1" : ""}`);
export const startBriefing = (sessionId: string) => apiSend<{ state: string }>("POST", `${roomPath(sessionId)}/briefing`);
export const getRoom = (sessionId: string, token?: string) => guestGet<RoomView>(`${roomPath(sessionId)}/lobby`, token);
export const livePath = (sessionId: string) => `${roomPath(sessionId)}/live`;
/** Open the link (no seat given) or take a seat. The code goes in the body; a stored token only in its header. */
export const joinRoom = (code: string, token?: string, seat?: { n: number; name: string; role: string }) =>
  guestSend<JoinView>("POST", `${BASE}/join`, seat ? { code, seat: seat.n, name: seat.name, role: seat.role } : { code }, token);

/** True for a pushed value that has the shape of a RoomView (the live stream sends unchecked JSON). */
export function asRoomView(raw: unknown): RoomView | null {
  if (typeof raw !== "object" || raw === null) return null;
  const v = raw as Partial<RoomView>;
  return typeof v.session_id === "string" && typeof v.state === "string" && Array.isArray(v.seats) ? (v as RoomView) : null;
}

// ---- M1-P09: the charter, signing in the room, the approver and the picture at sign-off ---------------------------
export type CharterStatus = "draft" | "awaiting_approver" | "signed" | "returned";
/** What a charter line needs to be shown: the same for the organiser and for the approver, who sees nothing more. */
export interface CharterLine {
  title: string;
  priority_label: string | null;
  so_that: string | null;
  note_count: number;
  /** Which of the four lists it belongs to; one drafted before kinds existed is a problem to solve now. */
  kind?: "intent" | "pain_point" | "future_signal" | "lever";
  /** What the notes of that kind said in their own details (who is affected, how often, the KPIs a lever moves...). */
  details?: { label: string; values: string[] }[];
}
export interface CharterDoc {
  version: number;
  template: { id: string; name: string; columns: string[] };
  problems: CharterLine[];
  later: { title: string }[];
  /** Notes that sat in no group: their words, or null for an anonymous note (a count only). The name only when posted by name. */
  alone?: { text: string | null; kind?: string; author_name?: string }[];
  /** The four lists in order, each with its heading: problems to solve now, pain points, what to track for the future, levers for what-if. */
  lists?: { kind: string; heading: string }[];
  footer: { date: string; participants: number; notes: number; later: number };
}
export interface CharterProblem extends CharterLine {
  id: string;
  priority: string | null;
  so_that_edited: boolean;
  so_that_proposal: string | null;
  /** True while the line is North's draft and no person has edited it. */
  so_that_draft?: boolean;
  /** The draft label, or (nothing drafted) the ask to the organiser; null when a person wrote the line. */
  so_that_note?: string | null;
  /** "Tied: must 1 · should 2 · could 2. The room decides." while the vote has no winner; null otherwise. */
  tie?: string | null;
  /** The options that tied: the organiser may choose among them before signing. */
  tied_options?: { id: string; label: string }[];
}
export interface Signer {
  name: string;
  at: string;
  how: "room" | "approver";
}
export interface CharterVersionRow {
  version: number;
  status: CharterStatus;
  created_at: string;
  created_by: string;
  edited_at: string | null;
  edited_by: string | null;
  comment: string | null;
}
export interface PictureGraph {
  label: string;
  problems: { id: string; title: string }[];
  kpis: { id: string; name: string }[];
  links: { problem: string; kpi: string }[];
}
export interface Charter extends CharterDoc {
  status: CharterStatus;
  problems: CharterProblem[];
  later: { id: string; title: string }[];
  signing: { needed: number; signed: number; can_sign: boolean; i_signed: boolean; signers: Signer[] };
  approver: { name: string; link: "none" | "open" | "expired" | "used" | "revoked"; expires_at: string | null };
  returned: { comment: string; by: string; at: string } | null;
  versions: CharterVersionRow[];
  editable: boolean;
  graph: PictureGraph | null;
  handed_on: boolean;
}
export interface CharterPage {
  state: string;
  organiser: boolean;
  can_draft: boolean;
  no_result: boolean;
  charter: Charter | null;
}
export interface SentToApprover extends CharterPage {
  link_path: string;
  link_expires_at: string;
}
export interface ApproverDraft extends CharterDoc {
  approver_name: string;
  expires_at: string;
}

const charterPath = (id: string) => `${sessionPath(id)}/charter`;
// a seated guest (a token, no account) reads the charter too, read-only, also after the close
export const getCharter = (id: string) => pGet<CharterPage>(id, charterPath(id));
/** Ends the room stage. `confirm` is true once the organiser has been asked about groups still open. */
export const makeCharterDraft = (id: string, confirm = false) => {
  const d = new Date(); // the organiser's own day goes on the charter's footer, not the server's UTC day
  const date = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  return apiSend<CharterPage>("POST", charterPath(id), confirm ? { confirm, date } : { date });
};
export const saveSoThat = (id: string, soThat: Record<string, string>) =>
  apiSend<CharterPage>("PUT", charterPath(id), { so_that: soThat });
/** "Use this line": the organiser accepts North's drafted lines as they stand. */
export const confirmSoThat = (id: string, problemIds: string[]) =>
  apiSend<CharterPage>("PUT", charterPath(id), { confirm_so_that: problemIds });
export const saveTiedPriority = (id: string, problemId: string, priority: string) =>
  apiSend<CharterPage>("PUT", charterPath(id), { priority: { [problemId]: priority } });
export const signCharter = (id: string) => apiSend<CharterPage>("POST", `${charterPath(id)}/sign`);
export const sendCharterUp = (id: string) => apiSend<SentToApprover>("POST", `${charterPath(id)}/send`);
export const withdrawCharterLink = (id: string) => apiSend<CharterPage>("POST", `${charterPath(id)}/withdraw`);
/** The signed charter as files built from the same view as the screen (a seated guest reads it with the token). */
export interface CharterFile {
  format: "html" | "markdown";
  filename: string;
  mime: string;
  content: string;
}
export const getCharterFiles = (id: string) => pGet<{ files: CharterFile[] }>(id, `${charterPath(id)}/download`);
/** A ready email for the organiser to copy. Nothing is sent; the people list has no address for a guest. */
export interface CharterEmail {
  subject: string;
  body: string;
  link_path: string;
  link: string;
  people: { name: string; email: string | null }[];
  no_address: string[];
}
export const getCharterEmail = (id: string) => apiGet<CharterEmail>(`${charterPath(id)}/email`);
// The approver has no account: the link's token goes in the same header the join token uses, and nowhere else.
export const getApproverDraft = (token: string) => guestSend<ApproverDraft>("POST", `${BASE}/approver/charter`, undefined, token);
export const decideCharter = (token: string, decision: "approve" | "decline", comment: string) =>
  guestSend<{ decision: string; status: CharterStatus }>("POST", `${BASE}/approver/decision`, { decision, comment }, token);

// ---- M1-P07: the board (M1-17 to M1-19) and back in the room (M1-20 to M1-23) ---------------------------------------
export interface BoardNote {
  id: string;
  text: string;
  anonymous: boolean;
  /** True only for the viewer's own notes. */
  mine: boolean;
  /** Only when the note was posted by name. */
  author_name?: string;
  /** Which of the four kinds of note it is; one with none is an intent. */
  kind?: "intent" | "pain_point" | "future_signal" | "lever";
}
export interface BoardCluster {
  id: string;
  name: string;
  source: "north" | "person" | "keywords";
  /** North's short reason for the group, shown as a suggestion. */
  reasoning: string;
  /** The kind of its notes; "mixed" when the organiser put kinds together by hand; null when empty. */
  kind?: "intent" | "pain_point" | "future_signal" | "lever" | "mixed" | null;
  note_ids: string[];
  notes: BoardNote[];
  /** Stable colour index 0-7 for this cluster. */
  colour?: number;
}
export interface BoardView {
  stage: string;
  paused_from: string | null;
  organiser: boolean;
  status: "none" | "done" | "failed";
  /** True when North could not answer and the groups were made from shared keywords: the organiser should check them. */
  grouped_without_north?: boolean;
  can_edit: boolean;
  can_restore: boolean;
  /** True once the organiser has changed North's grouping by hand. */
  edited: boolean;
  counts: { notes: number; clusters: number; on_its_own: number };
  /** How many notes there are of each kind. */
  by_kind?: Record<string, number>;
  /** The four kinds with the heading each has on the board and the charter. */
  kinds?: { id: "intent" | "pain_point" | "future_signal" | "lever"; heading: string }[];
  clusters: BoardCluster[];
  on_its_own: BoardNote[];
}
/** The organiser's live counts while the rooms are open. Never a note's words. */
export interface BoardCounts {
  stage: string;
  submitted: number;
  drafts: number;
  people_with_drafts: number;
}
export type VoteOption = "must" | "should" | "could" | "not_this_time";
export interface VoteChoice {
  id: VoteOption;
  label: string;
}
export interface TogetherComment {
  text: string;
  anonymous: boolean;
  author_name?: string;
}
export interface TogetherCluster {
  id: string;
  /** The topic of the session the cluster came from (IC-2g); null when it has none. */
  topic?: string | null;
  name: string;
  note_count: number;
  agree_count: number;
  comment_count: number;
  votes: Record<VoteOption, number>;
  vote_total: number;
  /** The one option with more votes than any other; null on a tie or when nobody has voted. */
  priority: VoteOption | null;
  ticked: boolean;
  /** Ticked into the charter by the room's vote (the organiser has not decided on it), and a tie the organiser breaks. */
  auto_ticked?: boolean;
  tie?: boolean;
  my_vote: VoteOption | null;
  my_agree: boolean;
  comments: TogetherComment[];
  notes: BoardNote[];
  /** The organiser's shelf, else the tally read as one; null when neither. `could` is served as good_to_have. */
  shelf?: ShelfId | null;
  shelf_reason?: string | null;
  review_date?: string | null;
  /** True when every measure behind the group is governed in module 2 (all six fields stated). Absent: no baseline or no measures yet. */
  governed?: boolean;
  /** The governed fields still not stated, across its measures (owners, classification, may_see, resolving, affects, review_date). */
  missing?: string[];
  /** Stable colour index (the board's), when served. */
  colour?: number;
  /** The measures this group maps to, when served (not served yet). */
  measure_codes?: string[];
}
export type ShelfId = "must" | "should" | "good_to_have" | "future";
export interface TogetherView {
  stage: string;
  paused_from: string | null;
  held: boolean;
  organiser: boolean;
  can_vote: boolean;
  options: VoteChoice[];
  clusters: TogetherCluster[];
  on_its_own_count: number;
  ticked_count: number;
  open_count: number;
  /** This person said "I'm done"; and how many of the people in the room (not the organiser) have. */
  i_done: boolean;
  done_count: number;
  people_count: number;
  /** The organiser's rule for names on notes and comments; missing means "choice". */
  names?: NamesRule;
  /** The module 2 baseline the measures belong to, when served (not served yet). */
  baseline_id?: string;
}

const boardPath = (id: string) => `${sessionPath(id)}/board`;
const togetherPath = (id: string) => `${sessionPath(id)}/together`;
const clusterPath = (id: string, clusterId: string) => `${togetherPath(id)}/clusters/${encodeURIComponent(clusterId)}`;
export const getBoard = (id: string) => pGet<BoardView>(id, boardPath(id));
export const getBoardCounts = (id: string) => apiGet<BoardCounts>(`${boardPath(id)}/counts`);
/** A participant's "I'm done" in the private rooms; the rooms close early when everyone seated has said it. */
export const sayRoomsDone = (id: string) => pSend<{ state: string }>(id, `${sessionPath(id)}/room/done`, { done: true });
export const closeRooms = (id: string) => apiSend<{ state: string }>("POST", `${sessionPath(id)}/rooms/close`);
export const groupNotes = (id: string) => apiSend<BoardView>("POST", `${boardPath(id)}/group`);
export const restoreGrouping = (id: string) => apiSend<BoardView>("POST", `${boardPath(id)}/restore`);
export const moveNote = (id: string, noteId: string, clusterId: string | null) =>
  apiSend<BoardView>("POST", `${boardPath(id)}/notes/${encodeURIComponent(noteId)}/move`, { cluster_id: clusterId });
export const renameCluster = (id: string, clusterId: string, name: string) =>
  apiSend<BoardView>("POST", `${boardPath(id)}/clusters/${encodeURIComponent(clusterId)}/rename`, { name });
export const splitCluster = (id: string, clusterId: string, noteIds: string[]) =>
  apiSend<BoardView>("POST", `${boardPath(id)}/clusters/${encodeURIComponent(clusterId)}/split`, { note_ids: noteIds });
export const addCluster = (id: string, name: string) => apiSend<BoardView>("POST", `${boardPath(id)}/clusters`, { name });
export const startTogether = (id: string) => apiSend<{ state: string }>("POST", togetherPath(id));
export const getTogether = (id: string) => pGet<TogetherView>(id, togetherPath(id));
export const voteOn = (id: string, clusterId: string, option: VoteOption | null) =>
  pSend<TogetherView>(id, `${clusterPath(id, clusterId)}/vote`, { option });
export const agreeWith = (id: string, clusterId: string, agree: boolean) =>
  pSend<TogetherView>(id, `${clusterPath(id, clusterId)}/agree`, { agree });
export const commentOn = (id: string, clusterId: string, text: string, anonymous: boolean) =>
  pSend<TogetherView>(id, `${clusterPath(id, clusterId)}/comments`, { text, anonymous });
export const tickCluster = (id: string, clusterId: string, ticked: boolean) =>
  apiSend<TogetherView>("POST", `${clusterPath(id, clusterId)}/tick`, { ticked });
/** The organiser puts a group on a shelf; Future needs a reason (the server sets the review date). */
export const shelveCluster = (id: string, clusterId: string, shelf: ShelfId, reason?: string) =>
  apiSend<TogetherView>("POST", `${clusterPath(id, clusterId)}/shelf`, reason === undefined ? { shelf } : { shelf, reason });
export const sayDone = (id: string, done: boolean) => pSend<TogetherView>(id, `${togetherPath(id)}/done`, { done });
export const holdRoom = (id: string) => apiSend<{ state: string; paused_from: string }>("POST", `${sessionPath(id)}/pause`);
export const resumeRoom = (id: string) => apiSend<{ state: string }>("POST", `${sessionPath(id)}/resume`);

// ---- the summary page: everything the room made, read-only, once the private rooms have closed ------------------
export interface SummaryNote {
  text: string;
  anonymous: boolean;
  author_name?: string;
  details: { label: string; values: string[] }[];
}
export interface SummaryPerson {
  name: string;
  role: string;
  notes: number;
  comments: number;
  votes: number;
}
export interface SummaryPage {
  session: { title: string; date: string; stage: string; names: NamesRule; people: { name: string; role: string }[]; people_count: number };
  intent: { id: string; label: string; items: { id: string; name: string; note_count: number; vote_total: number }[] }[];
  pain_points: SummaryNote[];
  future_signals: SummaryNote[];
  levers: SummaryNote[];
  board: BoardView;
  charter: Charter | null;
  can_download: boolean;
  contributions: {
    mode: NamesRule;
    totals: { notes: number; comments: number; votes: number };
    people: SummaryPerson[] | null;
    anonymous: { notes: number; comments: number; total: number } | null;
    small_group?: boolean;
  };
}
export const getSummary = (id: string) => pGet<SummaryPage>(id, `${sessionPath(id)}/summary`);
