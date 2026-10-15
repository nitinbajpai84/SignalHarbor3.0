import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError } from "../../api/client";
import Panel from "../../components/Panel";
import { copy } from "../../copy";
import { createDraft, startRoom, type Lists } from "./api";
import { m1, m1Lean } from "./copy";
import { formFromDraft, toPreparation } from "./form";
import { saveLink } from "./room/guestToken";

const D = m1Lean.drafted;
interface Row {
  label: string;
  value: string;
  source: string;
}

/**
 * LI-M1: Prepare opens drafted from the company profile (deck sample screen 6, "Your session, drafted"). Every line names where it
 * came from. One button makes the session and opens the room; "Change something" opens today's wizard with these values in it.
 */
export default function DraftedSession({ lists, onChange }: { lists: Lists; onChange: () => void }) {
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const f = lists.profile_draft?.fields ?? {};
  const rows: Row[] = [];
  const add = (label: string, v: { value: string; source: string } | undefined) => v && rows.push({ label, ...v });
  add(D.purpose, f.purpose);
  add(D.outcome, f.outcome);
  add(D.seats, f.seats && { value: D.people(f.seats.value), source: f.seats.source });
  add(D.approver, f.approver_name);
  add(D.names, f.names && { value: m1.wizard.namesOptions[f.names.value].label, source: f.names.source });
  add(D.length, f.length_minutes && { value: D.minutes(f.length_minutes.value), source: f.length_minutes.source });

  async function start() {
    setBusy(true);
    setError(null);
    try {
      const made = await createDraft(toPreparation(formFromDraft(lists)), true);
      const link = await startRoom(made.id);
      saveLink(made.id, link.join_path); // shown on the session page only; the server keeps just a hash of it
      navigate(`/modules/m1_intent/sessions/${encodeURIComponent(made.id)}`);
    } catch (e) {
      setError(e instanceof ApiError && e.message ? e.message : copy.errors.server);
      setBusy(false);
    }
  }

  return (
    <Panel title={D.title} className="m1-drafted">
      <p>{D.intro}</p>
      <dl className="m1-review">
        {rows.map((r) => (
          <div key={r.label}>
            <dt>{r.label}</dt>
            <dd>
              {r.value}
              <span className="m1-help">{D.from(r.source)}</span>
            </dd>
          </div>
        ))}
      </dl>
      {error ? (
        <p role="alert" className="state state-error">
          {error || D.failed}
        </p>
      ) : null}
      <p className="m1-actions">
        <button type="button" className="n-btn primary" disabled={busy} onClick={() => void start()}>
          {busy ? D.starting : D.looksRight}
        </button>
        <button type="button" className="n-btn" disabled={busy} onClick={onChange}>
          {D.change}
        </button>
      </p>
    </Panel>
  );
}
