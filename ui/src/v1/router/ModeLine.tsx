import { useModelMode } from "./ModeSwitch";

/** R1b: the one line under the agent's name on the four conversation screens. Nothing until the mode is read. */
export default function ModeLine() {
  const [state] = useModelMode();
  if (!state) return null;
  return <p className="ds-muted" style={{ margin: 0, fontSize: 12 }}>{state.mode === "real" ? "Real-use models" : "Testing models (free tier)"}</p>;
}
