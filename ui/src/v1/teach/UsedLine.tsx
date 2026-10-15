import type { Used } from "./api";

/** Under an agent's answer: which taught passages it quoted ("Used: Month end checks, passage 2"). Nothing when it used none. */
export default function UsedLine({ used }: { used?: Used[] | null }) {
  if (!used?.length) return null;
  return <p className="ds-muted" aria-label="Taught knowledge used" style={{ margin: "4px 0 0" }}>Used: {used.map((u) => `${u.title}, passage ${u.passage}`).join("; ")}</p>;
}
