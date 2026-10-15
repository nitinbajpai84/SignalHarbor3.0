import AgentChip, { type AgentName, type AgentStatus } from "./AgentChip";

interface Props {
  name: AgentName;
  status?: AgentStatus;
  /** One plain line on what this agent does here. */
  work: string;
  may?: string[];
  mayNot?: string[];
  /** Spoken names for the two lists (the tick and cross alone say nothing to a screen reader). */
  mayLabel: string;
  mayNotLabel: string;
}

/** The earlier prototype's roster card (screens/agent-roster.js agentCard): the agent chip, what it may and may not do, its work line. */
export default function AgentCard({ name, status = "idle", work, may = [], mayNot = [], mayLabel, mayNotLabel }: Props) {
  return (
    <div className="n-roster-card">
      <div className="rhead">
        <AgentChip name={name} status={status} />
      </div>
      <div className="permrow" role="group" aria-label={mayLabel}>
        {may.map((m) => (
          <div key={m} className="may">
            <span aria-hidden="true">✓ </span>
            {m}
          </div>
        ))}
      </div>
      <div className="permrow" role="group" aria-label={mayNotLabel}>
        {mayNot.map((m) => (
          <div key={m} className="maynot">
            <span aria-hidden="true">✗ </span>
            {m}
          </div>
        ))}
      </div>
      <div className="work">{work}</div>
    </div>
  );
}
