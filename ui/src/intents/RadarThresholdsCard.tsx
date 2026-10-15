import { useEffect, useState } from "react";

import { apiGet, apiSend } from "../api/client";
import { Button } from "../design";
import { T } from "./radarCopy";

// Spec 57 Screen D: the "Radar thresholds" card on the admin Defaults tab. Reads and writes settings.opportunity
// (existing four keys plus theme_min_voices, counter_periods, scan). No value is built in; empty means "Not set".
type Opp = Record<string, number | string | null>;
const whole = (v: string) => /^[1-9]\d*$/.test(v);

export function RadarThresholdsCard() {
  const [saved, setSaved] = useState<Opp | null>(null);
  const [vals, setVals] = useState<Record<string, string>>({});
  const [conf, setConf] = useState("");
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const apply = (o: Opp) => {
    setSaved(o); setConf(typeof o.min_confidence_to_show === "string" ? o.min_confidence_to_show : "");
    setVals(Object.fromEntries(T.keys.map(([k]) => [k, o[k] == null ? "" : String(o[k])])));
  };
  useEffect(() => { apiGet<{ opportunity?: Opp }>("/api/intents/settings").then((s) => apply(s.opportunity ?? {})).catch(() => apply({})); }, []);
  if (!saved) return null;
  const invalid = Object.values(vals).some((v) => v !== "" && !whole(v));
  const dirty = T.keys.some(([k]) => vals[k] !== (saved[k] == null ? "" : String(saved[k]))) || conf !== (typeof saved.min_confidence_to_show === "string" ? saved.min_confidence_to_show : "");
  const save = () => {
    const opportunity = { ...Object.fromEntries(T.keys.map(([k]) => [k, vals[k] === "" ? null : Number(vals[k])])), ...(conf ? { min_confidence_to_show: conf } : {}) };
    apiSend<{ opportunity?: Opp }>("PUT", "/api/intents/settings", { opportunity })
      .then((s) => { apply(s.opportunity ?? opportunity); setMsg({ ok: true, text: T.saved }); })
      .catch(() => setMsg({ ok: false, text: T.couldNot }));
  };
  return (
    <section className="ds-card ia-card" aria-label={T.card}>
      <h2>{T.card}</h2>
      <p className="ds-soft" style={{ margin: 0 }}>{T.note}</p>
      {T.keys.map(([k, label]) => (
        <label key={k} className="ia-box">
          <span>{label}</span>
          <span><input className="ia-field" inputMode="numeric" aria-label={label} value={vals[k] ?? ""} onChange={(e) => setVals({ ...vals, [k]: e.target.value })} style={{ width: 64, minHeight: 44 }} /></span>
          {(vals[k] ?? "") === "" && <span className="ia-grey">{T.unset}</span>}
        </label>
      ))}
      <label className="ia-box"><span>{T.conf}</span>
        <select aria-label={T.conf} value={conf} onChange={(e) => setConf(e.target.value)} style={{ minHeight: 44 }}>{T.confOptions.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select>
      </label>
      <div>
        <Button variant="primary" disabled={!dirty || invalid} onClick={save}>{T.save}</Button>{" "}
        {invalid ? <span role="alert" className="ia-amber">{T.bad}</span> : msg ? <span role={msg.ok ? "status" : "alert"}>{msg.text}</span> : null}
      </div>
    </section>
  );
}
