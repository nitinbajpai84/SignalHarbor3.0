// Shapes and words for the Build chain screens (docs/specs/intent-centre/59). Read from GET /api/company/build/changes, /changes/{id} and /architecture.
import type { PillTone } from "../../design";
import { day } from "../BuildCentre";

export type StepState = "waiting" | "drafting" | "with" | "signed" | "sent_back";
export interface Step { n: number; name: string; person: string | null; state: StepState; days: number | null; signed?: { by: string; at: string } | null }
export interface Back { from: number; to: number; by: string; reason: string; at: string }
export interface ChangeSummary { id: string; intent_id: string; title: string; state: string; step: number; steps: Step[]; last_return?: Back | null }
/** One line of a change note section. `group` names the view for "What changes"; `href` opens the item the line is about. */
export interface Line { text: string; mark?: "guessed" | "stated" | "unknown"; from?: string; group?: string; done?: boolean | null; href?: string }
export const SECTIONS = ["why", "what_changes", "decisions", "build_steps", "tests", "run_book", "risks"] as const;
export type SectionKey = typeof SECTIONS[number];
export interface Change extends ChangeSummary {
  sections: Record<SectionKey, Line[]>;
  returns: Back[];
  signatures: { step: number; name: string; role: string; at: string }[];
  handed?: { by: string; at: string } | null;
  release: { by: string; at: string } | null;
  build_progress?: { done: number; of: number } | null;
  /** North's completeness line for the approval step, and the first gap that disables the button. */
  completeness?: { line: string; gap: string | null } | null;
  /** The first thing that stops the current step's button, named; null when it may be pressed. */
  gate?: string | null;
  can_act: boolean;
  can_edit?: boolean;
  can_stop?: boolean;
  drafted_from?: string | null;
}

export const STEP_NAMES = ["Span, the architect", "Approval", "Span, the build agent", "Tester", "Ops manager"];
export const TITLES: Record<SectionKey, string> = {
  why: "Why", what_changes: "What changes", decisions: "Decision and alternatives", build_steps: "Build steps", tests: "What to test", run_book: "Run book additions", risks: "Risks",
};
export const EMPTY: Record<SectionKey, string> = {
  why: "Not available yet: this Initiative has no hypothesis. The change is checked against the catalogue only.",
  what_changes: "The Architect found nothing to add: every measure is adopted from existing tables.",
  decisions: "Not drafted yet.",
  build_steps: "No build steps: nothing to build for this change.",
  tests: "Nothing to test yet: the data engineer has not marked the build done.",
  run_book: "No run book change.",
  risks: "No accepted risk touches this change.",
};
export const NOT_NAMED = "Not named yet";
export const cc = {
  chainTitle: "The chain",
  chainLine: "Every change from an Initiative, step by step. Agents draft; the named person signs.",
  chainEmpty: "Nothing is being built. A change starts when an Initiative is handed to Build.",
  noLive: "No change is live yet.",
  nameThem: "Name them in the charter: Who does what",
  noArch: "No architecture recorded yet. The Architect drafts it when the first blueprint is signed.",
  retry: "Try again",
  notAvailable: "Not available yet. Try again in a moment.",
};

export const pillTone = (s: StepState): PillTone => (s === "signed" ? "signed" : s === "sent_back" ? "failed" : s === "with" || s === "drafting" ? "open" : "draft");
export const stateWord = (s: Step): string =>
  s.state === "signed" ? `Signed${s.signed?.at ? ` ${day(s.signed.at)}` : ""}` : s.state === "with" ? `With ${s.person ?? "nobody yet"}` : s.state === "sent_back" ? "Sent back" : s.state === "drafting" ? "Drafting" : "Waiting";
export const daysWord = (s: Step): string =>
  s.state === "signed" || s.state === "waiting" || s.days === null ? "Not started" : `With ${s.person ?? "nobody"} for ${s.days} working day${s.days === 1 ? "" : "s"}`;
export const backWord = (b: Back, names = STEP_NAMES): string => `Sent back by ${b.by}: ${b.reason} (to ${names[b.to - 1]?.toLowerCase() ?? "an earlier step"})`;
export const isOpen = (c: ChangeSummary): boolean => c.state !== "live" && c.state !== "stopped";
export const moment = (m: string): string => (m === "release_signed" ? "the release was signed" : m === "blueprint_signed" ? "the blueprint was signed" : m);
export const stepHref = (id: string, n: number) => `/centre/build/change/${encodeURIComponent(id)}?step=${n}`;
