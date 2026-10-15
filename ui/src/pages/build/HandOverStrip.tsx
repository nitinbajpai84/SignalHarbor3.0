import { Link } from "react-router-dom";

import { Chip } from "../../design";
import { useLoad } from "../BuildCentre";
import "./chain.css";
import { isOpen, stepHref, type ChangeSummary } from "./chain";

/** Screen D: one line under the title of Blueprint, Pipelines, Prove and Ops. Hidden when no change note is open. */
export default function HandOverStrip() {
  const { data } = useLoad<{ changes: ChangeSummary[] }>("/api/company/build/changes");
  const open = (data?.changes ?? []).filter(isOpen);
  const c = open[0];
  if (!c) return null;
  const s = c.steps.find((x) => x.n === c.step) ?? c.steps[0];
  return (
    <p className="bc-strip" aria-label="Where this change is">
      <span>Step {s?.n ?? c.step} of 5, {(s?.name ?? "").toLowerCase()}: {s?.person ?? "not named yet"}. Building against change note {c.id}.</span>
      <Link to={stepHref(c.id, c.step || 1)}>Open the change note</Link>
      {open.length > 1 ? <Chip href="/centre/build">{open.length} changes open</Chip> : null}
    </p>
  );
}
