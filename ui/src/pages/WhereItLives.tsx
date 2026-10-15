import { useState } from "react";
import { Link } from "react-router-dom";

import { ApiError, apiSend } from "../api/client";
import { Button } from "../design";
import { kmText as K } from "./knowledgeMapCopy";
import { whereRows, type KEdge, type KNode, type Overview } from "./knowledgeMap";

// The node page's "Where it lives" rows (spec 55, Screen B). Structure comes from the viewer's own map; scan result and owner kinds from the overview.
const P = K.panel;
export const SHOWN_FOR = ["Field", "File", "Source", "System", "Mart", "Measure"];
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const day = (iso: string | null) => { const d = iso ? new Date(iso) : null; return d && !Number.isNaN(d.getTime()) ? `${d.getDate()} ${MONTHS[d.getMonth()]}` : ""; };

function Row({ label, nodes, empty }: { label: string; nodes: KNode[]; empty: string }) {
  return (
    <div className="ds-where__row" style={{ display: "grid", gridTemplateColumns: "minmax(110px, 160px) 1fr", gap: 12, padding: "6px 0", fontSize: 15 }}>
      <span className="ds-muted">{label}</span>
      <span>{nodes.length
        ? nodes.map((n, i) => <span key={n.id}>{i > 0 && ", "}<Link className="ds-link" to={`/centre/intent/map/${encodeURIComponent(n.id)}`}>{n.label}</Link></span>)
        : <span className="ds-soft">{empty}</span>}</span>
    </div>
  );
}

export function WhereBody({ id, type, nodes, edges, ov, onChanged }: {
  id: string; type: string; nodes: KNode[]; edges: KEdge[]; ov: Overview | null; onChanged: () => void;
}) {
  const [asking, setAsking] = useState(false);
  const [reason, setReason] = useState("");
  const [note, setNote] = useState("");
  const w = whereRows(nodes, edges, id);
  const owners = ov?.owners?.[id] ?? [];
  const check = ov?.checks?.[id];
  const kinds = type === "Measure" ? ["business", "data"] : ["business", "data", "source"];
  async function answer(path: "confirm" | "reject") {
    setNote("");
    try {
      await apiSend("POST", `/api/intents/knowledge-map/${encodeURIComponent(id)}/${path}`, path === "reject" ? { reason } : undefined);
      setAsking(false);
      setReason("");
      setNote(P.saved);
      onChanged();
    } catch (e) { setNote(e instanceof ApiError ? e.message : P.failed); }
  }
  return (
    <div>
      {type === "System" ? <Row label={P.holds} nodes={w.holds} empty={P.noHolds} /> : <Row label={P.heldIn} nodes={w.heldIn} empty={P.noSystem} />}
      {type !== "System" && <Row label={P.landsAt} nodes={w.landsAt} empty={P.notRecorded} />}
      {type !== "System" && <Row label={P.writtenIn} nodes={w.writtenIn} empty={P.noDocument} />}
      {type === "Measure" ? <Row label={P.fedBy} nodes={w.fedBy} empty={P.noFedBy} /> : <Row label={P.feeds} nodes={w.feeds} empty={P.noFeeds} />}
      <Row label={P.producedBy} nodes={w.producedBy} empty={P.noProcess} />
      {type !== "System" && kinds.map((k) => {
        const named = owners.filter((o) => o.kinds.includes(k));
        return (
          <div key={k} className="ds-where__row" style={{ display: "grid", gridTemplateColumns: "minmax(110px, 160px) 1fr", gap: 12, padding: "6px 0", fontSize: 15 }}>
            <span className="ds-muted">{P.ownerKinds[k]}</span>
            <span>{named.length ? named.map((o) => o.label).join(", ") : <span className="ds-soft">{P.noOwner(P.ownerKinds[k] ?? k)}</span>}</span>
          </div>
        );
      })}
      {type !== "Measure" && type !== "System" && (
        <div className="ds-where__row" style={{ display: "grid", gridTemplateColumns: "minmax(110px, 160px) 1fr", gap: 12, padding: "6px 0", fontSize: 15 }}>
          <span className="ds-muted">{P.lastChecked}</span>
          <span>
            {check ? <>{P.checked(check.word, day(check.scanned_at), check.found_in?.label ?? null, check.confirmed_by)}{" "}
              <Link className="ds-link" to="/centre/build/gap-analysis">{P.openGap}</Link></>
              : <span className="ds-soft">{P.notChecked}</span>}
          </span>
        </div>
      )}
      <div className="ds-frame__actions" style={{ marginTop: 8 }}>
        <Link className="ds-btn" to={`/centre/intent/graph?view=lineage&focus=${encodeURIComponent(id)}`}>{P.showLineage}</Link>
        {check?.can_decide && !asking && <>
          <Button variant="primary" onClick={() => void answer("confirm")}>{P.confirm}</Button>
          <Button onClick={() => setAsking(true)}>{P.reject}</Button>
        </>}
      </div>
      {asking && (
        <div className="ds-comment__decide">
          <input aria-label={P.reason} placeholder={P.reason} value={reason} onChange={(e) => setReason(e.target.value)} />
          <Button variant="primary" disabled={!reason.trim()} onClick={() => void answer("reject")}>{P.send}</Button>
          <Button onClick={() => setAsking(false)}>{P.cancel}</Button>
        </div>
      )}
      {note && <p className="ds-soft" role="status">{note}</p>}
    </div>
  );
}
