import type { ReactNode } from "react";

import { Button, EmptyState } from "../../../design";
import { wallCopy as t } from "./copy";

/** Loading, error and refused for the wall and North's panel, from the design system: a skeleton, never a bare "Loading...". */
export default function WallState({ state, label, message, onRetry, skeleton = 4, children }: {
  state: "loading" | "empty" | "error" | "refused" | "populated"; label: string; message?: string; onRetry?: () => void; skeleton?: number; children?: ReactNode;
}) {
  if (state === "loading") {
    return (
      <div role="status" aria-label={label} className={`ds-wall-skeleton${skeleton === 1 ? " ds-wall-skeleton--north" : ""}`}>
        {Array.from({ length: skeleton }, (_, i) => <span key={i} />)}
      </div>
    );
  }
  if (state === "error" || state === "refused") {
    return (
      <div role="alert">
        <EmptyState title={message ?? t.failed} lines={[]} />
        {state === "error" && onRetry ? <Button onClick={onRetry}>{t.retry}</Button> : null}
      </div>
    );
  }
  return <>{children}</>;
}
