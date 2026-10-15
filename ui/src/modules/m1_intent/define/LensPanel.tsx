import { useEffect, useState } from "react";

import { ApiError } from "../../../api/client";
import { Button, EmptyState, Pill } from "../../../design";
import type { TogetherCluster } from "../api";
import { getGoverned, sendBackDefinition, type GovernedCell, type GovernedMeasure } from "../../m2_baseline/api";
import { confirmTechnical, getTechnical, type TechKpi, type TechPartView } from "../../m2_baseline/technical/technicalApi";
import { m1Define as d } from "./copy";

const SHOWN = ["sources", "fields", "calculation", "period", "currency_basis"] as const;
const L = d.lens;

type Kpi = TechKpi & { sent_back?: { note: string; label: string } | null };

function partText(p: TechPartView): string {
  const v = p.cell.value;
  return Array.isArray(v) ? v.join(", ") : v ? v : p.cell.from || d.notYet;
}

/** Module 2 keeps owners as {business, data, process} and who resolves it as {team, target_week}: show the values in order. */
export function cellText(c: GovernedCell | undefined): string {
  const v = c?.value;
  if (Array.isArray(v)) return v.length > 0 ? v.map(String).join(" · ") : c?.mark === "stated" ? L.noneNamed : d.notYet;
  if (typeof v === "string" || typeof v === "number") return String(v);
  if (v && typeof v === "object") {
    const parts = Object.entries(v as Record<string, unknown>).filter(([, x]) => x !== null && x !== undefined && x !== "").map(([k, x]) => (k.includes("week") ? `week ${String(x)}` : String(x)));
    if (parts.length > 0) return parts.join(" · ");
  }
  return d.notYet;
}

/** Lens for the selected cluster: each measure it maps to, with module 2's business and technical definition, where each came from,
 * and its governed state. A sealed cluster shows no definitions: the viewer is not on its list. */
export default function LensPanel({ baselineId, cluster, organiser, sealed = false }: { baselineId?: string; cluster: TogetherCluster | null; organiser: boolean; sealed?: boolean }) {
  const [kpis, setKpis] = useState<Kpi[] | null>(null);
  const [governed, setGoverned] = useState<GovernedMeasure[] | null>(null);
  const [noting, setNoting] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const codes = cluster?.measure_codes ?? [];
  const need = baselineId !== undefined && codes.length > 0 && !sealed;

  useEffect(() => {
    setKpis(null);
    setGoverned(null);
    setNoting(null);
    setError(null);
    if (!need) return;
    let live = true;
    getTechnical(baselineId)
      .then((t) => live && setKpis(t.kpis))
      .catch(() => live && setError(L.loadFailed));
    getGoverned(baselineId)
      .then((g) => live && setGoverned(g.measures))
      .catch(() => live && setGoverned(null));
    return () => {
      live = false;
    };
  }, [baselineId, need]);

  async function confirm(kpi: string) {
    setError(null);
    try {
      setKpis((await confirmTechnical(baselineId ?? "", kpi)).kpis);
    } catch (e) {
      setError(e instanceof ApiError && e.message ? e.message : L.confirmFailed);
    }
  }

  async function sendBack(kpi: string) {
    if (note.trim() === "") return setError(L.sendBackNeed);
    setError(null);
    try {
      setKpis((await sendBackDefinition(baselineId ?? "", kpi, note.trim())).kpis);
      setNoting(null);
      setNote("");
    } catch (e) {
      setError(e instanceof ApiError && e.message ? e.message : L.sendBackFailed);
    }
  }

  const shown = (kpis ?? []).filter((k) => codes.includes(k.kpi_id));
  return (
    <section className="df-lens" aria-label={L.title}>
      <div className="df-lens__head">
        <span className="df-lens__avatar" aria-hidden="true">L</span>
        <span className="df-lens__who">
          <strong>{L.title}</strong>
          <span>{need && codes[0] ? L.drafting(codes[0]) : L.role}</span>
        </span>
        <span style={{ marginLeft: "auto" }}><Pill tone="draft">{L.suggestion}</Pill></span>
      </div>
      {!cluster ? (
        <EmptyState title={L.pick} lines={[]} />
      ) : sealed ? (
        <EmptyState title={cluster.name} lines={[d.sealedLens]} />
      ) : (
        <>
          <h3 style={{ margin: 0, fontSize: 16 }}>{cluster.name}</h3>
          {!need ? <p className="ds-muted" style={{ margin: 0 }}>{L.noMeasures}</p> : null}
          {error ? <p role="alert" className="df-alert">{error}</p> : null}
          {shown.map((k) => (
            <section key={k.kpi_id} aria-label={k.name} className="df-lens">
              <div className="ds-card df-lens__card">
                <p className="df-eyebrow">{L.businessOf(k.kpi_id)}</p>
                <h4>{k.name}</h4>
                <p>{k.definition ?? d.notYet}</p>
              </div>
              <div className="ds-card df-lens__card">
                <p className="df-eyebrow">{L.technical}</p>
                <dl className="df-defs">
                  {k.parts.filter((p) => (SHOWN as readonly string[]).includes(p.part)).map((p) => (
                    <div key={p.part}>
                      <dt>{L.parts[p.part as (typeof SHOWN)[number]]}</dt>
                      <dd>{partText(p)}</dd>
                      <dd className="df-defs__mark">{`${L.marks[p.cell.mark]} · ${p.cell.by}`}</dd>
                    </div>
                  ))}
                </dl>
              </div>
              {k.sent_back ? <Pill tone="open">{k.sent_back.label}</Pill> : null}
              {k.confirmed !== null ? <Pill tone="signed">{L.confirmedPill}</Pill> : null}
              <div className="df-row">
                <Button variant="primary" disabled={!organiser || k.confirmed !== null} onClick={() => void confirm(k.kpi_id)}>{L.confirm}</Button>
                <Button disabled={!organiser} onClick={() => { setNoting(k.kpi_id); setNote(""); setError(null); }}>{L.sendBack}</Button>
              </div>
              {noting === k.kpi_id ? (
                <form className="df-lens" onSubmit={(e) => { e.preventDefault(); void sendBack(k.kpi_id); }}>
                  <label>
                    {L.sendBackLabel}
                    <input type="text" value={note} maxLength={300} onChange={(e) => setNote(e.target.value)} />
                  </label>
                  <div className="df-row">
                    <Button type="submit" variant="primary">{L.sendBackSend}</Button>
                    <Button onClick={() => setNoting(null)}>{L.sendBackCancel}</Button>
                  </div>
                </form>
              ) : null}
            </section>
          ))}
          {cluster.governed === undefined && (governed ?? []).length === 0 ? <p className="ds-muted" style={{ margin: 0 }}>{`${L.governedTitle}: ${d.notYet}`}</p> : null}
          {(governed ?? []).filter((g) => codes.includes(g.id)).map((g) => (
            <section key={g.id} aria-label={`${L.governedTitle}: ${g.name ?? g.id}`} className={`ds-card df-lens__card ${g.missing.length > 0 ? "df-lens__card--governed" : "df-lens__card--done"}`}>
              <p className="df-eyebrow">{L.governedTitle} · {g.name ?? g.id}</p>
              <strong>{L.governedCount(6 - g.missing.length)}</strong>
              <ul className="df-gov">
                {Object.keys(L.governedFields).map((f) => (
                  <li key={f} data-field={f} data-missing={g.missing.includes(f)}>
                    {`${L.governedFields[f]}: ${g.missing.includes(f) ? L.notSet : cellText(g.state[f])}`}
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </>
      )}
    </section>
  );
}
