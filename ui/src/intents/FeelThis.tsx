import { useEffect, useState } from "react";

import { apiGet, apiSend } from "../api/client";
import { Button } from "../design";
import { affectedCopy as t } from "./affectedCopy";

interface Mine { mine: { tapped: string[] } }

/** "I feel this" (spec 47, screens C and E). `item` is "intent" (a Problem) or a card id. Observers never see it: the page does not mount it
 * for them and the server refuses them anyway. One press opens the sign choice, the second counts; "Take it back" removes it. */
export default function FeelThis({ intentId, item, tapped }: { intentId: string; item: string; tapped?: boolean }) {
  const [on, setOn] = useState<boolean | null>(tapped ?? null);
  const [choosing, setChoosing] = useState(false);
  const [signed, setSigned] = useState(false);
  const [error, setError] = useState("");
  const base = `/api/intents/${encodeURIComponent(intentId)}`;

  useEffect(() => {
    if (tapped !== undefined) return;
    let live = true;
    apiGet<Mine>(`${base}/notes`).then((r) => live && setOn(r.mine.tapped.includes(item)), () => live && setOn(false));
    return () => { live = false; };
  }, [base, item, tapped]);

  const tap = async () => {
    setError("");
    try { await apiSend("POST", `${base}/feel`, { item, signed }); setOn(true); setChoosing(false); } catch { setError(t.saveError); }
  };
  const back = async () => {
    setError("");
    try { await apiSend("DELETE", `${base}/feel`, { item }); setOn(false); } catch { setError(t.saveError); }
  };

  return (
    <div className="feel-this">
      {on ? (
        <>
          <span className="n-muted" role="status">{t.tapped}</span>{" "}
          <Button onClick={back}>{t.takeBack}</Button>
        </>
      ) : (
        <Button aria-expanded={choosing} disabled={on === null} onClick={() => setChoosing(true)}>{t.feel}</Button>
      )}
      {choosing && !on && (
        <fieldset className="ds-card" style={{ padding: 12, marginTop: 8 }}>
          <legend className="n-muted">{t.feelTitle}</legend>
          <label style={{ display: "block", padding: "6px 0" }}>
            <input type="radio" name={`sign-${item}`} checked={!signed} onChange={() => setSigned(false)} /> {t.withoutName}
          </label>
          <label style={{ display: "block", padding: "6px 0" }}>
            <input type="radio" name={`sign-${item}`} checked={signed} onChange={() => setSigned(true)} /> {t.withName}
          </label>
          <Button variant="primary" onClick={tap}>{t.feel}</Button>{" "}
          <Button onClick={() => setChoosing(false)}>{t.cancel}</Button>
        </fieldset>
      )}
      {error && <p role="alert" className="state state-error">{error}</p>}
    </div>
  );
}
