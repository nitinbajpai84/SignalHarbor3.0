import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { ApiError } from "../../api/client";
import { Button, DataTable, EmptyState, PageFrame, Pill, type PillTone } from "../../design";
import { agreeScope, getScan, runScan, sendBack, type ScanStatus, type ScanView } from "./api";

const LOOK: Record<ScanStatus, { tone: PillTone; label: string }> = {
  available: { tone: "ok", label: "Available" },
  partly: { tone: "late", label: "Partly" },
  not: { tone: "failed", label: "Not available yet" },
};

/** /centre/build/:iid/scan: Span's scan per KPI; the decision maker agrees the scope or sends it back. */
export default function ScanPage() {
  const iid = useParams().iid ?? "";
  const [view, setView] = useState<ScanView | null>(null);
  const [scope, setScope] = useState<string[]>([]);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function act(fn: () => Promise<ScanView>) {
    setBusy(true);
    setError("");
    try {
      const v = await fn();
      setView(v);
      setScope(v.scan?.agreed?.scope ?? v.scan?.kpis.filter((k) => k.status === "available").map((k) => k.code) ?? []);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "That did not work. Please try again.");
    }
    setBusy(false);
  }

  useEffect(() => { void act(() => getScan(iid)); }, [iid]);

  const scan = view?.scan ?? null;
  const ready = scan?.kpis.filter((k) => k.status === "available").length ?? 0;
  const toggle = (code: string) => setScope((s) => (s.includes(code) ? s.filter((c) => c !== code) : [...s, code]));

  return (
    <PageFrame title="Scan and agree" subline="Span checked the landing files against the signed intent of work, KPI by KPI."
      actions={<Button onClick={() => act(() => runScan(iid))} disabled={busy}>{scan ? "Scan again" : "Run the scan"}</Button>}>
      <p className="ds-muted">Drafted by Span, the build agent{busy ? ": working…" : "."}</p>
      {error ? <p role="alert">{error}</p> : null}
      {!view ? null : !scan ? (
        <EmptyState title="Not scanned yet" lines={["Span reads the files in the landing area and says, per KPI, what can be built now."]} />
      ) : (
        <>
          <p><strong>These {ready} of {scan.kpis.length} can be built now.</strong> Scanned {scan.at.slice(0, 16).replace("T", " ")}.</p>
          <DataTable
            columns={[{ key: "pick", label: "In scope" }, { key: "kpi", label: "KPI" }, { key: "status", label: "Status" }, { key: "missing", label: "What is missing" }]}
            rows={scan.kpis.map((k) => ({
              pick: <input type="checkbox" aria-label={`Include ${k.code}`} checked={scope.includes(k.code)} disabled={k.status === "not" || busy}
                onChange={() => toggle(k.code)} />,
              kpi: <>{k.code} <span className="ds-muted">{view.names[k.code] ?? ""}</span></>,
              status: <Pill tone={LOOK[k.status].tone}>{LOOK[k.status].label}</Pill>,
              missing: k.missing.length ? <ul>{k.missing.map((m) => <li key={m.what}>{m.what}: expected in {m.where_expected}</li>)}</ul> : "Nothing",
            }))}
          />
          {scan.agreed ? <p>Agreed by {scan.agreed.by} on {scan.agreed.at.slice(0, 10)}: {scan.agreed.scope.join(", ")}.</p> : null}
          <div style={{ display: "flex", flexWrap: "wrap", gap: 12, marginTop: 16, alignItems: "flex-end" }}>
            <Button variant="primary" disabled={busy || scope.length === 0} onClick={() => act(() => agreeScope(iid, scope))}>
              Agree {scope.length} {scope.length === 1 ? "KPI" : "KPIs"}
            </Button>
            <label style={{ flex: "1 1 260px", display: "flex", flexDirection: "column", gap: 6 }}>
              What should change
              <input value={reason} onChange={(e) => setReason(e.target.value)} maxLength={500} />
            </label>
            <Button disabled={busy || !reason.trim()} onClick={() => act(() => sendBack(iid, reason.trim()))}>Send back</Button>
          </div>
        </>
      )}
    </PageFrame>
  );
}
