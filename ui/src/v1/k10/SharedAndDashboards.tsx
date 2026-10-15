import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { apiGet } from "../../api/client";
import { day } from "../../design";
import Comments from "../n2/Comments";
import type { SharedList } from "../cxui/api";

// Two sections of the Reports page: the dashboards that were published (approved in Build, one place to build them), and what was shared with the person.
interface Row { id: string; title: string; department?: string }
type Rep = { id: string; title: string; project_title: string; project_id?: string; tiles: number; link: string };

export function PublishedDashboards({ shared }: { shared: SharedList | null }) {
  const [projects, setProjects] = useState<Row[] | null>(null);
  useEffect(() => { apiGet<{ projects: Row[] }>("/api/v1/projects").then((r) => setProjects(r.projects), () => setProjects([])); }, []);
  // published dashboards (shared with you, then company-wide) grouped by department where the project has one, then by project
  const dept = (pid: string) => (projects ?? []).find((p) => p.id === pid)?.department ?? "";
  const seen = new Set<string>(), byDept = new Map<string, Map<string, Rep[]>>();
  for (const d of [...(shared?.dashboards ?? []), ...(shared?.company ?? [])] as Rep[]) {
    if (seen.has(d.id)) continue;
    seen.add(d.id);
    const g = byDept.get(dept(d.project_id ?? "")) ?? new Map<string, Rep[]>();
    g.set(d.project_title, [...(g.get(d.project_title) ?? []), d]);
    byDept.set(dept(d.project_id ?? ""), g);
  }
  const reports = [...byDept.entries()].sort(([a], [b]) => a.localeCompare(b));
  return (
    <section aria-label="Department and project reports">
      <h2 style={{ fontSize: 17 }}>Published dashboards</h2>
      <p className="ds-muted">A dashboard appears here once it has been approved in Build.</p>
      {shared === null ? <p className="ds-muted" role="status">Opening the dashboards.</p> : reports.length === 0 ? <p className="ds-muted">No dashboards have been published yet.</p> : null}
      {reports.map(([name, byProject]) => (
        <div key={name || "_"}>
          {name ? <h3>{name}</h3> : null}
          {[...byProject.entries()].map(([ptitle, boards]) => (
            <div key={ptitle}>
              <h4 style={{ margin: "8px 0 4px" }}>{ptitle}</h4>
              <ul style={{ listStyle: "none", padding: 0 }}>{boards.map((d) => (
                <li key={d.id}><Link className="ds-link" to={d.link}>{d.title}</Link> <span className="ds-muted">{d.tiles} tile{d.tiles === 1 ? "" : "s"}</span>
                  <Comments eager target={{ kind: "dashboard", id: d.id }} /></li>))}</ul>
            </div>))}
        </div>))}
      <p><Link className="ds-link" to="/centre/consume/design">Shape what you see</Link></p>
    </section>
  );
}

export function SharedWithYou({ shared }: { shared: SharedList | null }) {
  const none = shared && !shared.brief && shared.dashboards.length === 0;
  return (
    <section aria-label="Shared with you">
      <h2 style={{ fontSize: 17 }}>Shared with you</h2>
      {shared === null ? <p className="ds-muted" role="status">Opening what was shared with you.</p> : none ? <p className="ds-muted">Nothing has been shared with you yet.</p> : null}
      <ul style={{ listStyle: "none", padding: 0 }}>
        {shared?.brief ? <li><Link className="ds-link" to={shared.brief.link}>CIO Brief</Link> <span className="ds-muted">{shared.brief.title}</span></li> : null}
        {(shared?.dashboards ?? []).map((d) => (
          <li key={d.id}><Link className="ds-link" to={d.link}>{d.title}</Link> <span className="ds-muted">{d.project_title}, shared by {d.shared_by}, {day(d.shared_at)}, {d.tiles} tile{d.tiles === 1 ? "" : "s"}</span></li>
        ))}
      </ul>
    </section>
  );
}
