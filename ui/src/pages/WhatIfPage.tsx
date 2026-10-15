import { useEffect, useState, type CSSProperties } from "react";
import { useSearchParams } from "react-router-dom";

import { apiGet, apiSend } from "../api/client";
import { useSession } from "../useSession";
import { Button, Chip, EmptyState, Footnote, PageFrame, SideCard, Strip } from "../design";
import { RaiseFromWhatIf } from "./WhatIfRaise";
import { wire, type LensList } from "./consumeLens";

// What-if: one driver, a change in percent, and the measures it reaches along the map. Nothing is kept until you keep it.

interface GNode { id: string; type: string; label: string; restricted?: boolean }
interface Moved { code: string; label: string; path: string[]; change_pct: number; assumed_direction?: boolean; text?: string; latest: { period: string; value: number; moved_value: number } | null }
interface Saved { id: string; driver: string; change_pct: number; note: string; saved_at: string; result: Result }
interface Result { driver: string; moved: Moved[]; basis: string }

// ponytail: the design system has no form field yet; token colours only.
const FIELD: CSSProperties = { minHeight: 44, padding: "8px 12px", borderRadius: 8, border: "1px solid var(--ds-line-2)", background: "var(--ds-ground)", color: "var(--ds-ink)", font: "inherit", fontSize: 13, boxSizing: "border-box", width: "100%" };
const LABEL: CSSProperties = { display: "flex", flexDirection: "column", gap: 4, fontSize: 13, color: "var(--ds-ink-soft)" };
const LIST: CSSProperties = { listStyle: "none", margin: 0, padding: 0, display: "flex", flexDirection: "column", gap: 12 };
const ITEM: CSSProperties = { display: "flex", flexDirection: "column", gap: 6, paddingBottom: 12, borderBottom: "1px solid var(--ds-line)", fontSize: 14, color: "var(--ds-ink)" };

const signed = (n: number) => `${n > 0 ? "+" : ""}${n}%`;

export default function WhatIfPage() {
  const [drivers, setDrivers] = useState<GNode[] | null>(null);
  const [labels, setLabels] = useState<Record<string, string>>({});
  const [driver, setDriver] = useState("");
  const [pct, setPct] = useState(10);
  const [result, setResult] = useState<Result | null>(null);
  const [failed, setFailed] = useState(false);
  const [note, setNote] = useState("");
  const [saved, setSaved] = useState<Saved[]>([]);
  const { user } = useSession();
  const [sp] = useSearchParams();
  const lensKey = wire(sp.get("lens") ?? "");
  const [lensCodes, setLensCodes] = useState<string[]>([]);
  const [raising, setRaising] = useState(false), [raised, setRaised] = useState(false);
  const mayRaise = (user?.roles ?? []).some((x) => ["owner", "analyst", "sponsor", "company_admin"].includes(x));
  useEffect(() => {
    if (!lensKey) return;
    apiGet<LensList>("/api/company/consume/lenses").then((d) => setLensCodes(d.lenses.find((l) => l.key === lensKey)?.measures ?? [])).catch(() => undefined);
  }, [lensKey]);
  const mayKeep = (user?.roles ?? []).some((x) => ["sponsor", "analyst", "company_admin"].includes(x));
  const inLens = (d: GNode) => lensCodes.some((c) => d.id.toUpperCase().includes(c.toUpperCase()) || d.label.toUpperCase().includes(c.toUpperCase()));
  const name = (id: string) => labels[id] ?? id;
  const [savedFailed, setSavedFailed] = useState(false);
  const loadSaved = () => apiGet<{ scenarios: Saved[] }>("/api/company/whatif/kept").then((d) => { setSaved(d.scenarios); setSavedFailed(false); }).catch(() => setSavedFailed(true));
  const keep = () => apiSend("POST", "/api/company/whatif/keep", { driver, change_pct: pct, note }).then(() => { setNote(""); return loadSaved(); }).catch(() => setFailed(true));
  const drop = (id: string) => apiSend("DELETE", `/api/company/whatif/scenarios/${id}`).then(loadSaved).catch(() => setFailed(true));
  const rerun = (s: Saved) => { setDriver(s.driver); setPct(s.change_pct); setResult(null); };

  useEffect(() => {
    apiGet<{ nodes: GNode[] }>("/api/company/graph").then((g) => {
      setLabels(Object.fromEntries(g.nodes.map((n) => [n.id, n.label])));
      const seen = new Set<string>();  // the map holds each measure under a code and under a name: offer each label once, and not the unnamed cards
      setDrivers(g.nodes.filter((n) => !n.restricted && ["Measure", "Lever", "Field", "Problem"].includes(n.type) && n.label !== "A card" && !seen.has(n.label) && seen.add(n.label)));
    }).catch(() => { setDrivers([]); setFailed(true); });
  }, []);

  useEffect(() => { if (mayKeep) loadSaved(); }, [mayKeep]);  // a role that cannot keep has no list to read

  useEffect(() => {
    if (!driver) return;
    apiSend<Result>("POST", "/api/company/whatif", { driver, change_pct: pct }).then((r) => { setResult(r); setFailed(false); }).catch(() => setFailed(true));
  }, [driver, pct]);

  return (
    <PageFrame
      title="What-if"
      subline="Move one driver and see which of your measures move along the map. Nothing is kept until you keep it."
      aside={
        <SideCard title="Your scenarios">
          {savedFailed ? <p>Your scenarios could not be read just now. Try again in a moment.</p> : saved.length === 0 ? <p>You have not kept a scenario yet. Only you can see these.</p> : (
            <ul style={LIST}>
              {saved.map((s) => (
                <li key={s.id} style={ITEM}>
                  <strong>{name(s.driver)} {signed(s.change_pct)}</strong>
                  <Footnote>Kept {s.saved_at.slice(0, 10)}{s.note && ` · ${s.note}`}</Footnote>
                  <span style={{ fontSize: 13, color: "var(--ds-ink-soft)" }}>{s.result.moved.length ? s.result.moved.map((m) => m.text ?? m.label).join(" · ") : "No measure moved"}</span>
                  <span style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                    <Button aria-label={`Re-run ${name(s.driver)}`} onClick={() => rerun(s)}>Re-run</Button>
                    <Button aria-label={`Delete ${name(s.driver)}`} onClick={() => drop(s.id)}>Delete</Button>
                  </span>
                </li>
              ))}
            </ul>
          )}
        </SideCard>
      }
    >
      {drivers !== null && drivers.length === 0 && !failed
        ? <EmptyState title="No driver on your map yet" lines={["What-if moves a measure or a lever named on your map. Once the wall and the baseline add them, they appear here."]} links={[{ label: "Open the map", href: "/centre/intent/graph" }]} />
        : (
          <SideCard title="Pick a driver and a change">
            <label style={LABEL}>Driver
              <select style={FIELD} aria-label="Driver" value={driver} onChange={(e) => { setDriver(e.target.value); setResult(null); }}>
                <option value="">{drivers === null ? "Reading your map" : "Choose one"}</option>
                {[...(drivers ?? [])].sort((a, b) => Number(inLens(b)) - Number(inLens(a))).map((d) => <option key={d.id} value={d.id}>{d.label} ({d.type})</option>)}
              </select>
            </label>
            <label style={LABEL}>Change in percent
              <input style={FIELD} aria-label="Change in percent" type="number" min={-100} max={100} step={1} value={pct}
                onChange={(e) => { const n = Number(e.target.value); if (e.target.value !== "" && Number.isFinite(n)) setPct(n); }} />
            </label>
            <Footnote>The path comes from the map, and the estimate is a straight line.</Footnote>
          </SideCard>
        )}

      {failed && <div role="alert"><EmptyState title="This could not be worked out just now." lines={["Try again in a moment, or pick another driver."]} /></div>}

      {result && (
        <Strip label={`Driver · ${name(result.driver)} ${signed(pct)}`}>
          <SideCard title="What moves">
            {result.moved.length === 0 ? <><p><strong>Not available yet</strong></p><p>No measure is linked to this driver on your map, so there is no path to follow. Link it to a measure on the map and it will appear here.</p></> : (
              <ul style={LIST}>
                {result.moved.map((m) => (
                  <li key={m.code} style={ITEM}>
                    <span><strong>{m.label}</strong> <span className="ds-warn">{signed(Number(m.change_pct.toFixed(2)))}</span></span>
                    {m.latest
                      ? <span style={{ fontSize: 13, color: "var(--ds-ink-soft)" }}>{Number(m.latest.value.toFixed(2))} to {Number(m.latest.moved_value.toFixed(2))} ({m.latest.period})</span>
                      : <span style={{ fontSize: 13, color: "var(--ds-ink-muted)" }}>Not available yet</span>}
                    {m.assumed_direction && <span><Chip>assumed same way</Chip></span>}
                    <span style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>{m.path.map((p, i) => <Chip key={i}>{name(p)}</Chip>)}</span>
                  </li>
                ))}
              </ul>
            )}
            <Footnote>{result.basis}</Footnote>
            {mayKeep ? <>
              <label style={LABEL}>Note
                <input style={FIELD} aria-label="Note" value={note} maxLength={500} onChange={(e) => setNote(e.target.value)} placeholder="Why the committee should see this" />
              </label>
              <span><Button variant="primary" onClick={keep}>Keep this scenario</Button></span>
            </> : <Footnote>Your role can try a scenario but not keep one.</Footnote>}
            {mayRaise ? <>
              <span><Button disabled={result.moved.length === 0} onClick={() => setRaising(true)}>Turn this into an opportunity</Button></span>
              {result.moved.length === 0 ? <Footnote>Pick a driver whose path reaches a measure.</Footnote> : null}
              {raised ? <p role="status">Raised. It is on the opportunities list for review.</p> : null}
            </> : null}
          </SideCard>
          {raising ? <RaiseFromWhatIf driver={name(result.driver)} pct={pct} moved={result.moved} basis={result.basis} onClose={() => setRaising(false)} onRaised={() => { setRaising(false); setRaised(true); loadSaved(); }} /> : null}
        </Strip>
      )}
    </PageFrame>
  );
}
