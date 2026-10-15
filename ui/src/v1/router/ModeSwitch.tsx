import { useEffect, useState } from "react";

import { apiGet, apiSend } from "../../api/client";

// R1b: the Testing / Real use switch in the top bar. Every company role sees the state; the decision maker (company admin, sponsor)
// flips it, asked nothing; the next message in any conversation uses it. ModeLine shares the state through one window event.

export type ModelMode = "testing" | "real";
interface ModeState { mode: ModelMode; can_flip: boolean }
const EVENT = "sh-model-mode";
/** PF2: what the switch means, the same words in Settings and on the top bar. */
export const MODE_WORDS = "Testing: free model tier, for trying things. Real use: the company's chosen models. This switch applies to everyone in the company.";

/** The company's mode, kept in step with the switch. null until read (or when it cannot be read: nothing is shown). */
export function useModelMode(): [ModeState | null, (m: ModelMode) => Promise<void>] {
  const [state, setState] = useState<ModeState | null>(null);
  useEffect(() => {
    let live = true;
    apiGet<ModeState>("/api/v1/router/mode").then((s) => live && setState(s)).catch(() => undefined);
    const on = (e: Event) => setState((s) => ({ can_flip: s?.can_flip ?? false, mode: (e as CustomEvent<ModelMode>).detail }));
    window.addEventListener(EVENT, on);
    return () => { live = false; window.removeEventListener(EVENT, on); };
  }, []);
  const flip = async (mode: ModelMode) => {
    const got = await apiSend<ModeState>("POST", "/api/v1/router/mode", { mode });
    window.dispatchEvent(new CustomEvent<ModelMode>(EVENT, { detail: got.mode }));
  };
  return [state, flip];
}

const CSS = `
.ms-wrap{display:inline-flex;align-items:center;gap:6px;font-size:12px;color:var(--text-muted)}
.ms-wrap b{font-weight:600;color:var(--text-primary)}
.ms-track{position:relative;width:38px;height:22px;border-radius:11px;border:1px solid var(--border-hairline);background:var(--surface-elevated);padding:0;cursor:pointer;transition:background .2s}
.ms-track:disabled{cursor:default;opacity:.75}
.ms-track:focus-visible{outline:2px solid var(--teal);outline-offset:2px}
.ms-knob{position:absolute;top:2px;left:2px;width:16px;height:16px;border-radius:50%;background:var(--text-muted);transition:transform .2s,background .2s}
.ms-track[aria-checked="true"]{background:color-mix(in srgb,var(--teal) 30%,transparent)}
.ms-track[aria-checked="true"] .ms-knob{transform:translateX(16px);background:var(--teal)}
@media (prefers-reduced-motion: reduce){.ms-track,.ms-knob{transition:none}}
`;

export default function ModeSwitch() {
  const [state, flip] = useModelMode();
  const [busy, setBusy] = useState(false);
  if (!state) return null;
  const real = state.mode === "real";
  const toggle = () => {
    setBusy(true);
    flip(real ? "testing" : "real").catch(() => undefined).finally(() => setBusy(false));
  };
  const word = (on: boolean, text: string) => (on ? <b>{text}</b> : <span>{text}</span>);
  return (
    <span className="ms-wrap" title={MODE_WORDS + (state.can_flip ? "" : " Only the decision maker can change this.")}>
      <style>{CSS}</style>
      {word(!real, "Testing")}
      <button type="button" role="switch" className="ms-track" aria-checked={real} disabled={!state.can_flip || busy}
        aria-label={state.can_flip ? "Models: Testing or Real use" : `Models: ${real ? "Real use" : "Testing"}. Only the decision maker can change this.`}
        aria-description={MODE_WORDS} onClick={toggle}>
        <span className="ms-knob" aria-hidden="true" />
      </button>
      {word(real, "Real use")}
    </span>
  );
}
