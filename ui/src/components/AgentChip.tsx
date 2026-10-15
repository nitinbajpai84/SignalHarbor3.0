import { shellCopy } from "./shellCopy";

export type AgentName = keyof typeof shellCopy.agent.roles;
export type AgentStatus = keyof typeof shellCopy.agent.status;

interface Props {
  name: AgentName;
  status?: AgentStatus;
  /** Replaces the standard status word (for example "Answering your note"). */
  statusText?: string;
}

/** Ported from the earlier prototype's js/ui.js agentChip(): avatar ring with initials, name, role word, status. */
export default function AgentChip({ name, status = "idle", statusText }: Props) {
  return (
    <div className="n-agent-chip" data-agent={name}>
      <div className={`n-avatar-ring status-${status}`} aria-hidden="true">
        <div className="core">{name.slice(0, 2).toUpperCase()}</div>
        <div className="ring" />
      </div>
      <div className="meta">
        <div className="name">{name}</div>
        <div className="role">{shellCopy.agent.roles[name]}</div>
      </div>
      <div className={`status-text ${status}`}>{statusText ?? shellCopy.agent.status[status]}</div>
    </div>
  );
}
