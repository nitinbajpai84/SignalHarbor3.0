import { apiGet, apiSend } from "../../api/client";

// The Brainstorm calls (specs 35 and 36). One read feeds the session; every act is one POST to /session/<act>.

export interface Reply { id: string; text: string; author: string | null; anonymous: boolean; at: string; mine: boolean }
export interface Idea {
  id: string; text: string; why: string; anonymous: boolean; author: string | null; mine: boolean; at: string; edited: boolean;
  replies: Reply[]; group_id: string | null; group_name: string | null;
}
export interface Group { id: string; name: string; by: string; fallback: boolean; count: number }
export interface Prompt { text: string; drafted_by: string; edited_by: string | null; edited_at: string | null }
export interface Message { subject: string; body: string }
export interface Sess {
  id: string; title: string; purpose: string; state: string; role: "organiser" | "participant" | "observer";
  mode: "invitation" | "declined" | "before" | "live" | "closed";
  organiser?: string | null; statement: string | null; context: string | null; good_outcome: string | null; session_at: string | null; session_minutes: number | null;
  anonymous_allowed: boolean; window: { before: string; session: string; after: string } | null; starts: string | null; ends: string | null;
  my_status: string | null; counts: { total: number; invited: number; accepted: number; declined: number } | null;
  invited: { name: string; status: string; reason: string | null }[] | null; message: Message | null;
  phase?: "not_opened" | "diverge" | "group" | "converge" | "closed"; paused?: boolean; remaining_seconds?: number | null;
  prompts?: Partial<Record<"diverge" | "group", Prompt>>; north_lines?: string[]; ideas_count?: number | null; groups: Group[];
  here?: { n: number; total: number } | null; ideas_open?: boolean; grouped_by_words?: boolean; can_add?: boolean; ideas: Idea[];
  prethink?: { authors: number; ideas: number; invited: number }; decided_in?: { id: string; title: string }[];
}

const base = (id: string) => `/api/intents/${id}`;
export const brainstorm = {
  session: (id: string, display?: "projector") => apiGet<Sess>(`${base(id)}/session${display ? `?display=${display}` : ""}`),
  act: <T = { ok: boolean }>(id: string, act: string, body: Record<string, unknown> = {}) => apiSend<T>("POST", `${base(id)}/session/${act}`, body),
  reply: (id: string, card: string, body: { text: string; anonymous?: boolean }) => apiSend("POST", `${base(id)}/cards/${card}/replies`, body),
};

export interface Answers {
  statement?: string; context?: string; good_outcome?: string; people?: string[]; suggested?: string[]; areas?: string[]; session_date?: string;
  session_time?: string; session_minutes?: number | null; anonymous_ideas?: boolean; affected_may_read?: boolean; title?: string; purpose?: string;
  message?: Message; related?: Related[]; related_checked?: { at: string; shown: number; dismissed: boolean }; step?: string;
}
export interface Related { kind: string; ref: string; type: string; title: string; state: string; ends: string; why: string; used_as_context?: boolean; note?: string }
export interface Person { id: string; name: string; role: string; team: string; suggested: boolean; reason: string | null }
export interface PeopleAnswer { people: Person[]; areas: string[]; suggested_areas: string[] }
export interface Draft { start_answers?: Answers; title?: string; north_proposal?: { text?: string; title?: string } | null }
