import type { ReactNode } from "react";

export type PillTone = "success" | "warning" | "danger" | "info" | "muted";

/** The earlier prototype's statusPill(): n-pill with a tone dot. Colour never carries the meaning alone: the label does. */
export default function StatusPill({ tone = "muted", children }: { tone?: PillTone; children: ReactNode }) {
  return (
    <span className={`n-pill tone-${tone}`}>
      <span className="d" aria-hidden="true" />
      {children}
    </span>
  );
}
