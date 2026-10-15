import { useState } from "react";

import { Footnote, PageFrame, SideCard } from "../design";
import { useSession } from "../useSession";
import AgentMemory from "./AgentMemory";

// What the agents remember (a10.1): one list, the agent memory of mem_agent.py (/api/v1/memory/me and /company), grouped by the agent that
// learned each line: North, Span, Lumen and Tally. Company memory is read by everyone; the company administrator and analysts change it.
const EDITORS = ["company_admin", "analyst"];

function Tab({ selected, onClick, children }: { selected: boolean; onClick: () => void; children: string }) {
  return <button type="button" role="tab" aria-selected={selected} className={`ds-chip${selected ? " ds-chip--active" : ""}`} onClick={onClick}>{children}</button>;
}

export default function MemoryPage() {
  const { user } = useSession();
  const editor = !!user?.roles.some((r) => EDITORS.includes(r));
  const [tab, setTab] = useState<"me" | "company">("me");
  return (
    <PageFrame
      title="What the agents remember about you"
      subline={tab === "me" ? "What North, Span, Lumen and Tally remember about you" : "What the agents remember about the company"}
      actions={
        <div role="tablist" aria-label="Whose memory" className="ds-frame__actions">
          <Tab selected={tab === "me"} onClick={() => setTab("me")}>About me</Tab>
          <Tab selected={tab === "company"} onClick={() => setTab("company")}>Company memory</Tab>
        </div>
      }
      aside={
        <>
          <SideCard title="The context the agents use">
            <p>North (the intent agent), Span (the build agent), Lumen (the consume agent) and Tally (the data analyst in Action) read these lines before they answer you. Correct a line and they use your words; forget it and they stop using it.</p>
          </SideCard>
          {tab === "company" && (
            <SideCard title="Company memory">
              <p>Company memory has no names and no quotes. {editor ? "Edit or delete anything that is wrong." : "The company administrator or an analyst can change it."}</p>
            </SideCard>
          )}
          <Footnote>Anonymous notes, restricted areas, figures and contact details are never kept. Your edits are never overwritten.</Footnote>
        </>
      }
    >
      <AgentMemory company={tab === "company"} canEdit={editor} />
    </PageFrame>
  );
}
