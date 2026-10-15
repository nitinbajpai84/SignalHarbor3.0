import type { ReactNode } from "react";

import { copy } from "../copy";

export type ScreenStateName = "loading" | "empty" | "error" | "refused" | "populated";

interface Props {
  state: ScreenStateName;
  /** Replaces the default wording for the non-populated states. */
  message?: string;
  /** When given, the error state shows a "Try again" button that calls it. */
  onRetry?: () => void;
  children?: ReactNode;
}

export default function ScreenState({ state, message, onRetry, children }: Props) {
  switch (state) {
    case "populated":
      return <>{children}</>;
    case "loading":
      return (
        <p role="status" className="n-muted state">
          {message ?? copy.states.loading}
        </p>
      );
    case "empty":
      return (
        <div className="n-empty">
          <p className="ebody">{message ?? copy.states.empty}</p>
        </div>
      );
    case "error":
      return (
        <div>
          <p role="alert" className="state state-error">
            {message ?? copy.states.error}
          </p>
          {onRetry ? (
            <button type="button" className="n-btn" onClick={onRetry}>
              {copy.states.retry}
            </button>
          ) : null}
        </div>
      );
    case "refused":
      return (
        <p role="alert" className="state state-error">
          {message ?? copy.states.refused}
        </p>
      );
  }
}
