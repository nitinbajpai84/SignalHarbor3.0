import { useEffect, useState } from "react";

import { apiGet, Refused } from "../../api/client";
import { Button, SideCard } from "../../design";
import "./chain.css";
import { flowCopy } from "./flowCopy";

// Room 2: "SQL for your warehouse" (GET /api/company/build/dialect). Shown only when a warehouse target is stated.
interface Dialect { state?: string; message?: string; statements?: { name: string; sql: string }[] }
type Load = "loading" | "error" | "refused" | "ready";
const t = flowCopy.dialect;

export default function DialectPanel() {
  const [d, setD] = useState<Dialect | null>(null);
  const [load, setLoad] = useState<Load>("loading");
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let live = true;
    apiGet<Dialect>("/api/company/build/dialect").then((r) => { if (live) { setD(r); setLoad("ready"); } })
      .catch((e: unknown) => { if (live) setLoad(e instanceof Refused ? "refused" : "error"); });
    return () => { live = false; };
  }, [attempt]);
  if (load === "refused" || (load === "ready" && (!d?.state || d.state === "none"))) return null; // no target stated: nothing to translate, nothing to show
  if (load === "loading") return <SideCard title={t.title}><p role="status" className="ds-soft">{t.loading}</p></SideCard>;
  if (load === "error" || !d) return <SideCard title={t.title}><p role="alert" className="ds-warn">{t.error}</p><Button onClick={() => { setLoad("loading"); setAttempt((n) => n + 1); }}>Try again</Button></SideCard>;
  const stmts = d.statements ?? [];
  return (
    <SideCard title={t.title}>
      <p>{d.message ?? flowCopy.na}</p>
      {d.state === "ready" || d.state === "failed" ? (
        <>
          {stmts.length ? <p className="bc-note">{t.differs(stmts.length)}</p> : null}
          {stmts.map((s) => (
            <details key={s.name}><summary style={{ minHeight: 44, display: "flex", alignItems: "center" }}>{t.show}: {s.name.replace(/_/g, " ")}</summary><pre style={{ overflow: "auto", maxWidth: "100%" }}>{s.sql}</pre></details>
          ))}
          {d.state === "ready" ? <a className="ds-btn" href="/api/company/build/dialect/download" download>{t.download}</a> : null}
        </>
      ) : null}
    </SideCard>
  );
}
