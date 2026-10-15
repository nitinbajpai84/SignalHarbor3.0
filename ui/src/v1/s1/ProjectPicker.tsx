import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { apiGet } from "../../api/client";

// S1: the project picker used first by Build and Consume. Recent projects first, search by id or title, stage and owner shown.
export interface PickerProject {
  id: string; title: string; started_at?: string; started_by?: string | null; stage: string;
  people?: { sponsor?: string | null; raiser?: string | null };
}
const KEY = "sh-recent-projects";
export const STAGE_WORDS: Record<string, string> = {
  talking: "Intent: being drafted", signed: "Intent: signed", designed: "Build: design agreed", built: "Build: built", live: "Live",
};

const recents = (): string[] => {
  try { const v = JSON.parse(localStorage.getItem(KEY) ?? "[]"); return Array.isArray(v) ? v.map(String) : []; } catch { return []; }
};
const remember = (id: string) => {
  try { localStorage.setItem(KEY, JSON.stringify([id, ...recents().filter((x) => x !== id)].slice(0, 10))); } catch { /* storage blocked: order falls back to start date */ }
};

/** Most recently opened first, then newest started. Exported for its test. */
export function ordered(list: PickerProject[], seen: string[], q: string): PickerProject[] {
  const needle = q.trim().toLowerCase();
  const rank = (p: PickerProject) => { const i = seen.indexOf(p.id); return i < 0 ? seen.length : i; };
  return list
    .filter((p) => !needle || p.id.toLowerCase().includes(needle) || p.title.toLowerCase().includes(needle))
    .sort((x, y) => rank(x) - rank(y) || (y.started_at ?? "").localeCompare(x.started_at ?? ""));
}

/** A project opens at /centre/<centre>/p/<id>. Pass `projects` to skip the fetch. */
export default function ProjectPicker({ centre, projects }: { centre: "build" | "consume"; projects?: PickerProject[] }) {
  const [list, setList] = useState<PickerProject[] | null>(projects ?? null);
  const [failed, setFailed] = useState(false);
  const [q, setQ] = useState("");
  useEffect(() => {
    if (projects) { setList(projects); return; }
    let live = true;
    apiGet<{ projects: PickerProject[] }>("/api/v1/projects").then((r) => live && setList(r.projects)).catch(() => live && setFailed(true));
    return () => { live = false; };
  }, [projects]);
  const shown = useMemo(() => ordered(list ?? [], recents(), q), [list, q]);

  return (
    <section aria-label="Pick a project">
      <label>
        <span className="ds-footnote">Find a project by its number or title</span>
        <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="For example EV-0003 or monthly report" />
      </label>
      {failed ? <p role="alert">The projects could not be read. Please try again.</p> : null}
      {list && !shown.length ? <p className="ds-footnote">{list.length ? "No project matches that." : "There are no projects yet. Start one in the Intent centre."}</p> : null}
      <ul style={{ listStyle: "none", padding: 0, display: "grid", gap: 8 }}>
        {shown.map((p) => (
          <li key={p.id}>
            <Link to={`/centre/${centre}/p/${encodeURIComponent(p.id)}`} onClick={() => remember(p.id)}>
              <strong>{p.id}</strong> {p.title || "Untitled project"}
            </Link>
            <div className="ds-footnote">{STAGE_WORDS[p.stage] ?? p.stage} · Owner: {p.people?.sponsor ?? p.people?.raiser ?? p.started_by ?? "not set"}</div>
          </li>
        ))}
      </ul>
    </section>
  );
}
