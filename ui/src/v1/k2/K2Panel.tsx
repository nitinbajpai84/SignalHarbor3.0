import { useEffect, useState, type FormEvent } from "react";

import { ApiError, apiGet, apiSend } from "../../api/client";
import { Button } from "../../design";

// K2 The live company map as active knowledge context: a concept with its variants and the one-line difference, merge proposals a person
// confirms, and "Suggest a change" on any node (a suggestion to the definition's owner). Used by the map screen (M1).

export interface Variant { id: string; team: string; owner: string; project: string; definition: string; formula: string; unit: string; period: string; signed_on: string | null; version: number; why_different?: string | null }
export interface Concept { id: string; name: string; synonyms: string[]; variants: Variant[]; difference: string | null }
interface Proposal { id: string; from_name: string; into_name: string; reason: string; teams: string[] }

const KINDS: [string, string][] = [
  ["change_definition", "Change the definition"], ["rename", "Rename it"], ["add_synonym", "Add another name"],
  ["change_owner", "Change the owner"], ["merge", "Merge two concepts"], ["other", "Something else"],
];
const day = (iso: string | null) => (iso ? new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short" }) : "");

export function ConceptView({ concept }: { concept: Concept }) {
  return (
    <div>
      {concept.variants.length > 1 && <p><strong>{concept.variants.length} variants.</strong> {concept.difference}</p>}
      <ul>
        {concept.variants.map((v) => (
          <li key={v.id}>
            <strong>{v.team || v.owner}</strong> <span className="ds-muted">({v.project}{v.signed_on ? `, signed ${day(v.signed_on)}` : ""}{v.version > 1 ? `, version ${v.version}` : ""}; owner {v.owner || "not named"})</span>
            <br />{v.definition || "Not defined yet."}{v.why_different ? <span className="ds-muted"> Different because: {v.why_different}</span> : null}
          </li>
        ))}
      </ul>
    </div>
  );
}

export function ConceptAnswers({ concepts, onPick }: { concepts: Concept[]; onPick: (id: string) => void }) {
  return (
    <>{concepts.map((c) => (
      <div key={c.id}>
        <p><button type="button" className="ds-link" onClick={() => onPick(c.id)}><strong>{c.name}</strong></button> <span className="ds-muted">(concept)</span></p>
        <ConceptView concept={c} />
      </div>
    ))}</>
  );
}

export function SuggestChange({ node, isConcept }: { node: string; isConcept: boolean }) {
  const [open, setOpen] = useState(false);
  const [kind, setKind] = useState("change_definition");
  const [value, setValue] = useState("");
  const [other, setOther] = useState("");
  const [text, setText] = useState("");
  const [msg, setMsg] = useState("");
  const [all, setAll] = useState<Concept[]>([]);
  useEffect(() => {
    if (kind === "merge") apiGet<{ concepts: Concept[] }>("/api/v1/map/concepts").then((r) => setAll(r.concepts ?? [])).catch(() => setAll([]));
  }, [kind]);
  const kinds = KINDS.filter(([k]) => isConcept || k !== "merge");
  const needsValue = kind !== "merge" && kind !== "other";

  async function send(e: FormEvent) {
    e.preventDefault();
    try {
      await apiSend("POST", "/api/v1/map/suggestions", { node, kind, value, other, text });
      setOpen(false); setValue(""); setText(""); setMsg("Sent to the owner. They accept it or tell you why not.");
    } catch (err) { setMsg(err instanceof ApiError ? err.message : "Your suggestion could not be sent. Please try again."); }
  }
  return (
    <div>
      {open ? (
        <form onSubmit={send}>
          <select aria-label="What would you change" value={kind} onChange={(e) => setKind(e.target.value)}>
            {kinds.map(([k, label]) => <option key={k} value={k}>{label}</option>)}
          </select>
          {needsValue && <input aria-label="The new text" placeholder="The new text" value={value} maxLength={500} onChange={(e) => setValue(e.target.value)} />}
          {kind === "merge" && (
            <select aria-label="The other concept" value={other} onChange={(e) => setOther(e.target.value)}>
              <option value="">Merge with…</option>
              {all.filter((c) => c.id !== node).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          )}
          <textarea aria-label="Why" placeholder="Why, in a sentence" value={text} maxLength={500} onChange={(e) => setText(e.target.value)} />
          <Button type="submit" variant="primary" disabled={!(text.trim() || value.trim())}>Send</Button> <Button onClick={() => setOpen(false)}>Cancel</Button>
        </form>
      ) : <Button onClick={() => { setOpen(true); setMsg(""); }}>Suggest a change</Button>}
      {msg && <p className="ds-soft" role="status">{msg}</p>}
    </div>
  );
}

export function Proposals() {
  const [rows, setRows] = useState<Proposal[]>([]);
  const [attempt, setAttempt] = useState(0);
  const [msg, setMsg] = useState("");
  useEffect(() => { apiGet<{ proposals: Proposal[] }>("/api/v1/map/proposals").then((r) => setRows(r.proposals ?? [])).catch(() => setRows([])); }, [attempt]);
  async function decide(id: string, confirm: boolean) {
    try { await apiSend("POST", `/api/v1/map/proposals/${encodeURIComponent(id)}`, { confirm }); setMsg(""); setAttempt((a) => a + 1); }
    catch (err) { setMsg(err instanceof ApiError ? err.message : "That could not be saved. Please try again."); }
  }
  if (rows.length === 0) return null;
  return (
    <div className="ds-card ds-side">
      <p><strong>Possibly the same measure</strong></p>
      <ul>{rows.map((p) => (
        <li key={p.id}>{p.from_name} and {p.into_name}. <span className="ds-muted">{p.reason}</span>{" "}
          <Button onClick={() => decide(p.id, true)}>Yes, merge them</Button> <Button onClick={() => decide(p.id, false)}>Not the same</Button></li>
      ))}</ul>
      {msg && <p className="ds-soft" role="status">{msg}</p>}
    </div>
  );
}

export function useConcept(id: string | null): Concept | null {
  const [c, setC] = useState<Concept | null>(null);
  useEffect(() => {
    setC(null);
    if (id) apiGet<Concept>(`/api/v1/map/concepts/${encodeURIComponent(id)}`).then(setC).catch(() => setC(null));
  }, [id]);
  return c;
}
