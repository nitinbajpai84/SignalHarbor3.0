import type { ReactNode } from "react";

import { copy } from "../copy";
import AgentChip, { type AgentName } from "./AgentChip";
import Icon from "./Icon";
import Panel from "./Panel";
import { shellCopy } from "./shellCopy";

export interface WizardStep {
  id: string;
  label: string;
}

interface Props {
  title: string;
  steps: WizardStep[];
  /** Index of the current step. */
  current: number;
  /** Next stays off until the step says it is ready. */
  ready: boolean;
  onBack: () => void;
  onNext: () => void;
  /** Agent text for this step, shown with a visible "Suggestion" tag. */
  suggestion?: string;
  /** The agent who is with the person on this step (its presence chip is shown above the step). */
  agent?: AgentName;
  children: ReactNode;
}

/**
 * The wizard frame. The step strip is the earlier prototype's journey bar (n-journey: done, current and upcoming steps with
 * separators and a "step n of m" note); the suggestion is its copper "you decide" block (n-suggest-block).
 */
export default function WizardFrame({ title, steps, current, ready, onBack, onNext, suggestion, agent, children }: Props) {
  const last = current >= steps.length - 1;
  return (
    <Panel title={title} eyebrow={shellCopy.stepOf(current + 1, steps.length)} className="wizard">
      <div className="n-journey wizard-journey">
        <ol className="n-journey-steps wizard-steps" aria-label={copy.wizard.steps}>
          {steps.map((s, i) => {
            const state = i < current ? "done" : i === current ? "current" : "upcoming";
            return (
              <li key={s.id} className="n-journey-item" aria-current={i === current ? "step" : undefined}>
                <span className={`n-journey-step ${state}`}>
                  {state === "done" ? <Icon name="check" size={12} /> : null}
                  {s.label}
                </span>
                {i < steps.length - 1 ? <span className="n-journey-sep" aria-hidden="true" /> : null}
              </li>
            );
          })}
        </ol>
      </div>
      <div className="wizard-body">
        {agent ? <AgentChip name={agent} status="waiting" /> : null}
        {suggestion ? (
          <div className="n-suggest-block wizard-suggestion">
            <div className="n-suggest-label">{copy.wizard.suggestion}</div>
            <p>{suggestion}</p>
          </div>
        ) : null}
        {children}
      </div>
      <div className="wizard-nav">
        <button type="button" className="n-btn" onClick={onBack} disabled={current <= 0}>
          {copy.wizard.back}
        </button>
        {last ? null : ( // the last step brings its own primary action (for module 1: save, then continue)
          <button type="button" className="n-btn primary" onClick={onNext} disabled={!ready}>
            {copy.wizard.next}
          </button>
        )}
      </div>
    </Panel>
  );
}
