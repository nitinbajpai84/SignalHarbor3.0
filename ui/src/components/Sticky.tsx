import type { ReactNode } from "react";

export type StickyTone = "yellow" | "teal" | "slate" | "copper";

interface Props {
  /** yellow: a person's own note; teal: a group or a session; slate: a neutral card; copper: a suggestion. */
  tone?: StickyTone;
  contested?: boolean;
  /** The note's own words, set in italic Fraunces. */
  question?: ReactNode;
  children?: ReactNode;
  className?: string;
}

/** The earlier prototype's sticky note, verbatim markup: n-sticky n-sticky-<tone> with an n-sticky-q line. */
export default function Sticky({ tone = "yellow", contested = false, question, children, className }: Props) {
  const cls = `n-sticky n-sticky-${tone}${contested ? " n-sticky-contested" : ""}${className ? ` ${className}` : ""}`;
  return (
    <div className={cls}>
      {question !== undefined ? <div className="n-sticky-q">{question}</div> : null}
      {children}
    </div>
  );
}
