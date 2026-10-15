import Panel from "../../components/Panel";
import { m1 } from "./copy";
import type { Lists, SessionView } from "./api";

/** A session that has started: its preparation values, read-only (M1-01). */
export default function SessionSummary({ session, lists }: { session: SessionView; lists: Lists }) {
  const p = session.preparation;
  const W = m1.wizard;
  return (
    <Panel title={m1.summary.title} className="m1-summary">
      <p className="state n-muted" role="status">
        {m1.summary.started}
      </p>
      <dl className="m1-review">
        <dt>{m1.labels.purpose}</dt>
        <dd>{p.purpose}</dd>
        <dt>{m1.labels.outcome}</dt>
        <dd>{p.outcome || W.noValue}</dd>
        <dt>{m1.labels.charter}</dt>
        <dd>{lists.charter_templates.find((t) => t.id === p.charter_template)?.name ?? W.noValue}</dd>
        <dt>{m1.labels.seats}</dt>
        <dd>{p.seats === 1 ? W.seatsSolo : W.seatsMany(p.seats)}</dd>
        <dt>{m1.labels.length}</dt>
        <dd>{W.minutes(p.length_minutes)}</dd>
        <dt>{m1.labels.split}</dt>
        <dd>
          {W.splitPart.briefing} {p.split.briefing}, {W.splitPart.individual} {p.split.individual}, {W.splitPart.together}{" "}
          {p.split.together}
        </dd>
        <dt>{m1.labels.practice}</dt>
        <dd>{p.north_industry_practice ? W.yes : W.no}</dd>
        <dt>{m1.labels.library}</dt>
        <dd>{p.north_problem_library ? W.yes : W.no}</dd>
        <dt>{m1.labels.video}</dt>
        <dd>{W.videoOptions[p.briefing_video] ?? W.videoOther}</dd>
        <dt>{m1.labels.names}</dt>
        <dd>{W.namesOptions[p.names ?? "choice"].label}</dd>
        <dt>{m1.labels.approver}</dt>
        <dd>{p.approver_name || W.noValue}</dd>
      </dl>
    </Panel>
  );
}
