import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { apiGet, apiSend } from "../api/client";
import { Button } from "../design";

// North's opening line in the chooser (spec 46): "Last time you ..." from what North remembers about this person, with where it came from.
// Nothing shows when North remembers nothing. Same shape again starts a draft of that kind; Not this time hides the line for this visit.

interface Opening { line: string | null; type?: string; preference?: string | null }

export default function MemoryOpening() {
  const nav = useNavigate();
  const [o, setO] = useState<Opening | null>(null);
  const [hidden, setHidden] = useState(false);
  const [err, setErr] = useState(false);
  useEffect(() => { apiGet<Opening>("/api/intents/opening-line").then(setO, () => setO(null)); }, []);
  if (!o?.line || hidden) return null;
  const again = async () => {
    setErr(false);
    try {
      const made = await apiSend<{ id: string }>("POST", "/api/intents", { type: o.type });
      nav(`/centre/intent/new?type=${o.type}&draft=${made.id}`);
    } catch { setErr(true); }
  };
  return (
    <div role="region" aria-label="What North remembers">
      <p>{o.line} <Link className="ds-link" to="/centre/memory">Memory</Link></p>
      {o.preference && <p className="ds-soft">{o.preference}</p>}
      {err && <p role="alert" className="state state-error">We could not start that. Please try again.</p>}
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <Button style={{ minHeight: 44 }} onClick={() => void again()}>Same shape again</Button>
        <Button style={{ minHeight: 44 }} onClick={() => setHidden(true)}>Not this time</Button>
      </div>
    </div>
  );
}
