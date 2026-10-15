import { useCallback, useEffect, useState } from "react";

import { ApiError } from "../api/client";
import { Button, Footnote, Pill, SideCard, Signature } from "../design";
import { countersign, getGoverned, getReview, sendBackDefinition, type GovernedView, type SignoffView } from "../modules/m2_baseline/api";

const day = (iso: string) => new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" });
const PCT: [keyof GovernedView["percentages"], string][] = [["owned", "Owned"], ["classified", "Classified"], ["may_see_confirmed", "Who may see it confirmed"], ["sealed", "Sealed"]];
/** The six governed-state fields (GovernedMeasure.missing, api.ts) in plain words; an unknown name shows as sent. */
const FIELD: Record<string, string> = { owners: "owners", classification: "classification", may_see: "who may see", resolving: "resolving team", affects: "affected downstream", review_date: "review date" };
const BAR = { width: "100%", accentColor: "var(--ds-teal)" } as const;

/** One panel: the gate (every Must measure governed, four percentages as bars), who signs and in what order, Sign for the next person,
 * the signed (read-only) state, and send back with a note. */
export default function BaselineSignoff({ baselineId }: { baselineId: string }) {
  const [view, setView] = useState<SignoffView | null>(null);
  const [gov, setGov] = useState<GovernedView | null>(null);
  const [failed, setFailed] = useState<"no" | "yes" | "refused">("no");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const [sendKpi, setSendKpi] = useState("");
  const [note, setNote] = useState("");
  const [sent, setSent] = useState(false);

  const load = useCallback(async () => {
    try {
      const [v, g] = await Promise.all([getReview(baselineId), getGoverned(baselineId)]);
      setView(v);
      setGov(g);
      setFailed("no");
    } catch (e) {
      setFailed(e instanceof ApiError && e.status === 403 ? "refused" : "yes");
    }
  }, [baselineId]);
  useEffect(() => void load(), [load]);

  if (failed === "refused") return null; // a role that does not see the sign-off (participant) gets no panel at all
  if (failed === "yes") return <SideCard title="Baseline sign-off"><p role="alert">The sign-off could not be loaded. Please try again.</p><div><Button onClick={() => void load()}>Try again</Button></div></SideCard>;
  if (!view || !gov) return <SideCard title="Baseline sign-off"><Footnote>Opening the sign-off.</Footnote></SideCard>;

  const must = view.kpis.filter((k) => k.priority === "must");
  const governed = new Map(gov.measures.map((m) => [m.id, m]));
  const missing = must.filter((k) => !governed.get(k.id)?.governed);
  const gateOk = missing.length === 0 && view.gate?.ok !== false;
  const signed = view.status === "signed";
  const canSign = !signed && !!view.viewer.slot && view.can_countersign;

  async function act(work: () => Promise<unknown>, after?: () => void) {
    if (busy) return;
    setBusy(true);
    setProblem(null);
    try {
      await work();
      after?.();
      await load();
    } catch {
      setProblem("That did not go through. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <SideCard title="Baseline sign-off">
      <div><Pill tone={signed ? "signed" : gateOk ? "open" : "draft"}>{signed ? "Signed" : gateOk ? "Ready to sign" : "Not ready to sign"}</Pill></div>

      <strong>Is every Must measure governed?</strong>
      <p>{must.length ? `${must.length - missing.length} of ${must.length} Must measures governed` : "No Must measure is in this baseline yet."}</p>
      {missing.length ? (
        <ul aria-label="Not governed yet">
          {missing.map((k) => (
            <li key={k.id}>{`${k.name}: ${(governed.get(k.id)?.missing.map((f) => FIELD[f] ?? f) ?? ["not in the governed record"]).join(", ")} not stated yet`}</li>
          ))}
        </ul>
      ) : null}
      <ul aria-label="Governed share" style={{ listStyle: "none", padding: 0 }}>
        {PCT.map(([key, label]) => (
          <li key={key}>
            <span>{`${label}: ${gov.percentages[key]}%`}</span>
            <progress value={gov.percentages[key]} max={100} aria-label={label} style={BAR} />
          </li>
        ))}
      </ul>
      {!signed && view.gate && !view.gate.ok ? <p role="note">{view.gate.refusal}</p> : null}

      <strong>Who signs</strong>
      <Footnote>The sponsor signs first, then the head of data, as two different people.</Footnote>
      {view.signatures.map((s) => <Signature key={s.slot} state="signed" by={`${s.name} (${s.label})`} at={day(s.at)} />)}
      {view.waiting_for.map((l, i) => (
        <Signature key={l} state="waiting" by={l} onSign={i === 0 && canSign && gateOk ? () => void act(() => countersign(baselineId)) : undefined} />
      ))}

      {signed ? (
        <p role="status">This baseline is signed and read-only. Changes need a new version.</p>
      ) : canSign && !gateOk ? (
        <Footnote>You can sign once every Must measure is governed.</Footnote>
      ) : !canSign ? (
        <Footnote>You are not the next person to sign.</Footnote>
      ) : null}

      {!signed ? (
        <>
          <strong>Send back with a note</strong>
          <Footnote>The note waits beside the measure for its owner; the definition is not changed.</Footnote>
          <select aria-label="Measure to send back" value={sendKpi} onChange={(e) => setSendKpi(e.target.value)}>
            <option value="">Choose a measure</option>
            {view.kpis.map((k) => <option key={k.id} value={k.id}>{k.name}</option>)}
          </select>
          <input type="text" aria-label="Note for the data owner" placeholder="What needs another look" value={note} onChange={(e) => setNote(e.target.value)} />
          <Button disabled={busy || !sendKpi || !note.trim()} onClick={() => void act(() => sendBackDefinition(baselineId, sendKpi, note.trim()), () => { setNote(""); setSent(true); })}>
            Send back with a note
          </Button>
          {sent ? <p role="status">Sent back. The note waits beside the definition.</p> : null}
        </>
      ) : null}
      {problem ? <p role="alert">{problem}</p> : null}
    </SideCard>
  );
}
