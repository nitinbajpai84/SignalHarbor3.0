import { useState, type ComponentType } from "react";

import { Button } from "../../design";

// "Where is this from?" opens the trail panel built by card A2 (ui/src/v1/a5trail/TrailPanel.tsx). Loaded by glob so this folder
// builds whether or not A2 has landed; until it has, the person is told so in words.
export interface TrailProps { kind: string; id: string; onClose: () => void }
const found = import.meta.glob<{ default: ComponentType<TrailProps> }>("../a5trail/TrailPanel.tsx", { eager: true });
const Panel = Object.values(found)[0]?.default;

export function WhereFrom({ kind, id }: { kind: string; id: string }) {
  const [open, setOpen] = useState(false);
  return (
    <span>
      <Button onClick={() => setOpen(!open)} aria-expanded={open}>Where is this from?</Button>
      {open ? (Panel ? <Panel kind={kind} id={id} onClose={() => setOpen(false)} />
        : <p className="ds-muted" role="status">The trail for this is not available yet.</p>) : null}
    </span>
  );
}
