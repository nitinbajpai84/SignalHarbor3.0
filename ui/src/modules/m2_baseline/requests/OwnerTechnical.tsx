import { useState } from "react";

import { ApiError } from "../../../api/client";
import Panel from "../../../components/Panel";
import type { TechKpi } from "../technical/technicalApi";

const WORDS = {
  title: "Technical definitions you own",
  help: "You are named as the data owner of these. Read how each is worked out and confirm it if it is right; to change it, tell the person who asked you.",
  notAvailable: "Not available yet",
  withheld: "Part of this is limited to people named for it.",
  confirm: "Confirm this technical definition",
  confirmedBy: (by: string) => `Confirmed by ${by}.`,
  needsAgain: (parts: string) => `Changed since you confirmed it: ${parts}.`,
  incomplete: (parts: string) => `Not complete yet: ${parts}.`,
  failed: "That could not be confirmed. Please try again.",
  signInTitle: "Technical definitions to confirm after signing in",
  signInNote: "You have an account, so please sign in to confirm the technical definition of these measures:",
  signIn: "Sign in",
};

const asText = (v: unknown) => (Array.isArray(v) ? v.join(", ") : v == null ? "" : String(v));

/** The technical definitions of the measures this person is the named data owner of (on their answer link, or signed in). An owner with no account reads and
 * confirms them here; an owner with an account is told to sign in. Only their own measures appear, worded for them. */
export default function OwnerTechnical({ technical, onConfirm, signIn = [], signInPath, locked }: { technical: TechKpi[]; onConfirm: (kpiId: string) => Promise<TechKpi[]>; signIn?: { kpi_id: string; name: string }[]; signInPath?: string; locked: boolean }) {
  const [items, setItems] = useState(technical);
  const [problem, setProblem] = useState<string | null>(null);
  if (items.length === 0 && signIn.length === 0) return null;
  const confirm = async (kpiId: string) => {
    setProblem(null);
    try {
      setItems(await onConfirm(kpiId));
    } catch (e) {
      setProblem(e instanceof ApiError && e.message && e.status < 500 ? e.message : WORDS.failed);
    }
  };
  return (
    <>
      {items.length > 0 ? (
        <Panel title={WORDS.title}>
          <p className="n-e1-def-note">{WORDS.help}</p>
          {items.map((k) => (
            <section key={k.kpi_id} aria-label={k.name}>
              <h3>{k.name}</h3>
              <dl>
                {k.parts.map((p) => (
                  <div key={p.part}>
                    <dt>{p.label}</dt>
                    <dd>{p.withheld ? WORDS.withheld : p.links.length ? p.links.map((l) => l.name).join(", ") : asText(p.cell.value) || WORDS.notAvailable}</dd>
                  </div>
                ))}
              </dl>
              {k.confirmed ? <p><strong>{WORDS.confirmedBy(k.confirmed.by)}</strong></p> : null}
              {!k.confirmed && k.to_confirm?.length ? <p className="n-muted">{WORDS.needsAgain(k.to_confirm.join(", "))}</p> : null}
              {!k.complete ? <p className="n-muted">{WORDS.incomplete(k.missing.join(", "))}</p> : null}
              {!k.confirmed && k.complete ? (
                <button type="button" className="n-btn sm primary" disabled={locked} aria-label={`${WORDS.confirm}: ${k.name}`} onClick={() => void confirm(k.kpi_id)}>
                  {WORDS.confirm}
                </button>
              ) : null}
            </section>
          ))}
          {problem ? <p role="alert" className="state state-error">{problem}</p> : null}
        </Panel>
      ) : null}
      {signIn.length > 0 && signInPath ? (
        <Panel title={WORDS.signInTitle}>
          <p className="n-e1-def-note">{WORDS.signInNote} {signIn.map((s) => s.name).join(", ")}</p>
          <a className="n-btn" href={`/login?next=${encodeURIComponent(signInPath)}`}>{WORDS.signIn}</a>
        </Panel>
      ) : null}
    </>
  );
}
