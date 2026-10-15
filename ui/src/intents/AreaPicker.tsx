import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { apiGet, apiSend } from "../api/client";
import Panel from "../components/Panel";
import { Button, Chip } from "../design";

/** The area picker (spec 05, component C): "Who is this about?" in every start flow, and "Change areas" on an intent.
 *  `value` is the chosen area ids. `suggestion` is North's line, given by the start screen once participants are named
 *  (their names and the area ids their tags give); nothing is added without the click. `affectedMayRead` only words the strip. */

interface Area { id: string; name: string }
interface Listing { areas: Area[]; can_set_up: boolean; reach?: { count: number | null; missing: string | null } }

export interface AreaPickerProps {
  value: string[];
  onChange: (ids: string[]) => void;
  suggestion?: { names: string[]; areaIds: string[] };
  affectedMayRead?: boolean;
}

const joined = (xs: string[]) => (xs.length < 2 ? xs.join("") : `${xs.slice(0, -1).join(", ")} and ${xs[xs.length - 1]}`);

export default function AreaPicker({ value, onChange, suggestion, affectedMayRead = false }: AreaPickerProps) {
  const [list, setList] = useState<Listing | null>(null);
  const [failed, setFailed] = useState(false);
  const [query, setQuery] = useState("");
  const [skipped, setSkipped] = useState(false);
  const key = value.join(",");

  useEffect(() => {
    let live = true;
    apiGet<Listing>(`/api/intents/areas${key ? `?pick=${encodeURIComponent(key)}` : ""}`).then((r) => { if (live) { setList(r); setFailed(false); } }).catch(() => { if (live) setFailed(true); });
    return () => { live = false; };
  }, [key]);

  if (failed) return <p role="alert" className="ds-warn">The areas could not be loaded. Please try again.</p>;
  if (!list) return <p role="status" className="n-muted">Loading areas.</p>;
  if (list.areas.length === 0) {
    return (
      <p className="n-muted">
        Your admin has not set up areas yet.{list.can_set_up ? <> <Link to="/centre/intent/admin/areas">Set up areas</Link></> : null}
      </p>
    );
  }
  const name = (id: string) => list.areas.find((a) => a.id === id)?.name ?? id;
  const toggle = (id: string) => onChange(value.includes(id) ? value.filter((i) => i !== id) : [...value, id]);
  const offered = list.areas.filter((a) => a.name.toLowerCase().includes(query.trim().toLowerCase()));
  const add = suggestion ? suggestion.areaIds.filter((i) => !value.includes(i) && list.areas.some((a) => a.id === i)) : [];

  let strip: string;
  if (value.length === 0) strip = "Pick an area to see how many people it reaches.";
  else if (!list.reach || list.reach.count === null) strip = `Not available yet: ${(list.reach?.missing ?? "no people file read").replace(/^No/, "no")}`;
  else {
    strip = `People in ${joined(value.map(name))} will see that this exists, its title, purpose, stage and outcome: ${list.reach.count} people. Only people you name open the content.`;
    if (affectedMayRead) strip += " Affected people may read it too.";
  }

  return (
    <div>
      <div role="group" aria-label="Areas" style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 8 }}>
        {value.map((id) => <Chip key={id} tone="active" onClick={() => toggle(id)}>{name(id)} (remove)</Chip>)}
      </div>
      <input type="search" aria-label="Search areas" placeholder="Search areas" value={query} onChange={(e) => setQuery(e.target.value)} />
      <div style={{ display: "flex", flexWrap: "wrap", gap: 6, margin: "8px 0" }}>
        {offered.map((a) => <Chip key={a.id} tone={value.includes(a.id) ? "active" : "default"} onClick={() => toggle(a.id)}>{a.name}</Chip>)}
      </div>
      {value.length === 0 ? <p className="n-muted">Pick at least one area to continue.</p> : null}
      {add.length > 0 && !skipped ? (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center" }}>
          <span>North suggests: {joined(suggestion!.names)} {suggestion!.names.length > 1 ? "are" : "is"} in {joined(add.map(name))}. Add {add.length > 1 ? "both" : "it"}?</span>
          <Button variant="primary" onClick={() => onChange([...value, ...add])}>Add</Button>
          <Button onClick={() => setSkipped(true)}>No</Button>
        </div>
      ) : null}
      <Panel title="Who will see this"><p>{strip}</p></Panel>
    </div>
  );
}

/** "Change areas" on an existing intent: the picker, then Save with the Confirm step. The count line comes from the server's reach figure
 *  for the old and the new pick; where either is not known the confirm says so instead of a number. */
export function ChangeAreas({ intentId, current, onDone }: { intentId: string; current: string[]; onDone: () => void }) {
  const [value, setValue] = useState(current);
  const [confirming, setConfirming] = useState(false);
  const [delta, setDelta] = useState<string>("");
  const [error, setError] = useState("");
  const reach = (ids: string[]) => apiGet<Listing>(`/api/intents/areas?pick=${encodeURIComponent(ids.join(","))}`).then((r) => r.reach?.count ?? null);

  const review = async () => {
    const [before, after] = await Promise.all([reach(current), reach(value)]);
    setDelta(before === null || after === null ? "Not available yet: no people file read" : after >= before ? `${after - before} more people will see this` : `${before - after} people will stop seeing this`);
    setConfirming(true);
  };
  const save = () => apiSend("PUT", `/api/intents/${intentId}/areas`, { areas: value }).then(onDone).catch((e: Error) => setError(e.message));

  return (
    <div>
      <AreaPicker value={value} onChange={(v) => { setValue(v); setConfirming(false); }} />
      {confirming ? <p role="status">{delta}. Confirm?</p> : null}
      {error ? <p role="alert" className="ds-warn">{error}</p> : null}
      <Button variant="primary" disabled={value.length === 0 || value.join() === current.join()} onClick={() => void (confirming ? save() : review())}>{confirming ? "Confirm" : "Change areas"}</Button>
    </div>
  );
}
