// Screen words for Span's panels on the blueprint screen (SF16). Plain words: no table names, ids or codes. Every agent draft is a suggestion.

export const sc = {
  fallback: "Span could not reach the model. This is the rule-based draft.",
  loading: "Reading Span's records",
  retry: "Try again",
  error: "This could not be read just now. Try again in a moment.",
  refused: "You cannot ask Span for a draft.",
  notArchitect: "Only the change's architect can ask Span for this.",
  tag: "Span's suggestion",
  statedTag: "Stated by a person",
  // model draft
  modelTitle: "Span's model draft",
  modelLine: "Span, the solution architect, drafts the clean data model and the finished measures, and test-builds them in a safe copy before anyone sees them.",
  modelEmpty: "No model draft yet. Ask Span to draft the model.",
  askModel: "Ask Span to draft the model",
  askRevise: "Ask Span to revise",
  reviseLabel: "What should Span change?",
  file: "File for signature",
  drafting: "Span is drafting the model. This page updates by itself.",
  filed: (v: number) => `Filed into version ${v} of the blueprint. Check it, then sign.`,
  skipped: "Lines a person has stated were kept as they are.",
  rounds: (n: number) => `${n} ${n === 1 ? "round" : "rounds"} in the sandbox`,
  errorsTitle: "Why it did not build",
  questionsTitle: "Span's open questions",
  builtTitle: "What built",
  // suggestions
  sugTitle: "Span's suggestions to the data team",
  sugLine: "Span suggests; the named person decides. Nothing is applied until they accept.",
  sugEmpty: "Span has no suggestions right now.",
  review: "Ask Span to review the model",
  reviewFallback: "Span could not review the model just now. Try again later.",
  forWho: (name: string, role: string) => `For ${name}, the ${role}, to decide`,
  waitingOn: (name: string) => `${name} decides this.`,
  accept: "Accept",
  decline: "Decline",
  ask: "Ask a question",
  reasonLabel: "Why do you decline it?",
  questionLabel: "Your question for Span",
  send: "Send",
  cancel: "Cancel",
  what: "What",
  why: "Why",
  evidence: "Evidence",
  impact: "What it touches",
  alternatives: "Other options",
  effort: "Effort",
  technique: "Technique",
  accepted: "Accepted. A change note opens for it.",
  declined: "Declined.",
  asked: "Question sent.",
  thread: "Questions asked",
  // design document
  designTitle: "Design document",
  designLine: "Drafted by Span from the signed records. It is signed together with the blueprint.",
  designEmpty: "No design document yet. Span drafts it when a change note is filed.",
  draftBanner: "Draft",
  signedBanner: (name: string, day: string) => `Signed by ${name} on ${day}`,
  download: "Download the design document",
  downloadSpec: "Download the spec",
  uploadSpec: "Upload the spec",
  uploadedSpec: "The spec was saved as stated by you.",
  specBad: "That file is not a spec Span can read. Download the spec, change it and upload it again.",
  redraft: "Ask Span to redraft",
  redrafting: "Span is redrafting the design document.",
  diagramOf: "Diagram of the architecture",
  diagramMissing: "Not available yet: the diagram could not be drawn.",
  tabs: { current: "Current", target: "Target", delta: "What changes" },
  notYet: "Not available yet",
};

/** The template's section titles, in page order (sh_platform/build/agents/design_template.yaml). */
export const SECTIONS: [string, string][] = [
  ["purpose", "Purpose and scope"], ["context", "Context from the charter"], ["current", "Current state"], ["target", "Target architecture"],
  ["delta", "What changes"], ["model", "Data model and modelling technique"], ["layers", "Layers: landed, cleaned, finished"],
  ["sources", "Sources and their strategic flags"], ["flows", "Data flows"], ["security", "Security and the egress boundary"],
  ["quality", "Quality and testing"], ["operations", "Operations"], ["decisions", "Decisions and alternatives"],
  ["risks", "Risks and open questions"], ["suggestions", "Suggestions for the data team"],
];

/** Words for what a code or table name stands for: snake_case read as words, a leading dim_ or fact_ and a gold. prefix dropped, measure codes left out. */
export function plain(text: string): string {
  return text
    .replace(/\bType [12] (?:SCD|slowly changing dimension)s?\b/gi, "history-keeping setup")
    .replace(/\bslowly changing dimensions?\b/gi, "history of changes")
    .replace(/\bSCDs?\b/g, "history of changes")
    .replace(/\bconformed dimensions\b/gi, "shared lists")
    .replace(/\bmarts\b/gi, "report tables")
    .replace(/\b(?:bronze|silver) layer\b/gi, "cleaned layer")
    .replace(/\bgold\.[a-z]\d+\.(\w+)/gi, "$1")
    .replace(/\bgold\.[a-z]\d+\b/gi, "")
    .replace(/\b(?:dim|fact)_(\w+)/g, "$1")
    .replace(/\b[a-z]+(?:_[a-z]+)+\b/g, (m) => m.replace(/_/g, " "))
    .replace(/\b[A-Z]-?\d{2,6}\b:?,?\s*/g, "")
    .replace(/\s{2,}/g, " ")
    .replace(/\s+([,.;:])/g, "$1")
    .trim();
}

/** A design line without its leading id ("N-0001: title" reads "title"). */
export const line = (text: string) => plain(text.replace(/^[A-Z]-\d+:\s*/, ""));

export const EFFORT: Record<string, string> = { small: "Small", medium: "Medium", large: "Large" };
