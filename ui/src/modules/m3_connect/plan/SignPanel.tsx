import Panel from "../../../components/Panel";
import StatusPill from "../../../components/StatusPill";
import { planCopy as T } from "./copy";
import type { PlanView } from "./planApi";

const day = (iso: string) => (Number.isNaN(new Date(iso).getTime()) ? "" : new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" }));

/** The sign panel: the sponsor signs, then the head of data. The button is there only for the person whose turn it is. */
export default function SignPanel({ plan, busy, onSign }: { plan: PlanView; busy: boolean; onSign: () => void }) {
  const slot = plan.viewer.slot;
  return (
    <Panel title={T.sign.title} actions={<StatusPill tone={plan.signed_at ? "success" : "warning"}>{plan.signed_at ? "Signed" : "Not signed yet"}</StatusPill>}>
      {plan.signed_at ? <p role="status">{T.sign.signed}</p> : <p className="n-muted">{T.sign.help}</p>}
      <ul>
        {plan.signatures.map((s) => (
          <li key={s.slot}>
            {T.sign.signedBy(s.name, s.label, day(s.at))}
            {s.note ? <span className="n-e1-def-note"> ({s.note})</span> : null}
          </li>
        ))}
      </ul>
      {!plan.signed_at && plan.waiting_for.length ? <p className="n-e1-def-note">{T.sign.waitingFor(plan.waiting_for.join(", "))}</p> : null}
      {!plan.signed_at && plan.risks_undecided > 0 ? <p role="status" className="state n-muted">{T.sign.risksOpen(plan.risks_undecided)}</p> : null}
      {!plan.signed_at && plan.restricted_hidden > 0 ? <p className="n-e1-def-note">{T.sign.hidden(plan.restricted_hidden)}</p> : null}
      {!plan.signed_at && plan.drafted ? (
        slot ? (
          <button type="button" className="n-btn primary" disabled={busy || !plan.can_sign} onClick={onSign}>
            {T.sign.signAs[slot]}
          </button>
        ) : (
          <p className="n-e1-def-note">{T.sign.notYourTurn}</p>
        )
      ) : null}
    </Panel>
  );
}
