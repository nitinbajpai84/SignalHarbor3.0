import { useEffect, useState } from "react";

import { Chip, DataTable, Footnote, PageFrame, StatCard, StatGrid } from "../../design";
import AskLumen from "./AskLumen";
import FundLeague from "./FundLeague";
import IndexMapPanel from "./IndexMapPanel";
import { getHealth, type Health as HealthData, type Trust } from "./api";
import { Loading, NOT_YET, Status, WhereLink, money, pct, plain, pts, signed } from "./format";

// Financial health: the detail behind Today. One table with a level switch: each portfolio, each entity, each fund (the fund league), and how far each value is trusted.
type Level = "portfolio" | "entity" | "fund";
const LEVELS: [Level, string][] = [["portfolio", "By portfolio"], ["entity", "By entity"], ["fund", "By fund"]];

const Num = ({ children }: { children: string }) => <span style={{ fontVariantNumeric: "tabular-nums" }}>{children}</span>;
const Dash = () => <span className="ds-muted">–</span>;
const TrustCell = ({ t }: { t: Trust }) => <><Status s={t.status} />{t.detail ? <div className="ds-muted" style={{ fontSize: "0.85rem" }}>{t.detail}</div> : null}</>;
const signedOrDash = (v: string | null) => (v === null ? <Dash /> : <Num>{signed(v)}</Num>);

export default function Health({ ccy }: { ccy: string }) {
  const [h, setH] = useState<HealthData | null>(null);
  const [error, setError] = useState("");
  const [level, setLevel] = useState<Level>("portfolio");
  useEffect(() => {
    let live = true;
    setH(null); setError("");
    getHealth(ccy).then((r) => { if (live) setH(r); }, (e) => { if (live) setError(plain(e)); });
    return () => { live = false; };
  }, [ccy]);
  if (error) return <PageFrame title="Financial health"><p role="alert">{error}</p></PageFrame>;
  if (!h) return <PageFrame title="Financial health"><Loading what="financial health" /></PageFrame>;
  const f = h.funds;
  const portfolioRows = h.portfolios.map((r) => ({
    pf: <>{r.portfolio}<div className="ds-muted" style={{ fontSize: "0.85rem" }}>{r.entity}</div><WhereLink label={r.portfolio} where={r.where} id={r.trail_id} /></>,
    value: r.value === null ? NOT_YET : <Num>{money(r.value)}</Num>, pnl: signedOrDash(r.pnl), ret: r.return_pct === null ? <Dash /> : <Num>{pct(r.return_pct)}</Num>,
    vs: r.ahead_pts === null ? <Dash /> : <span title={r.benchmark_label ?? undefined}><Num>{pts(r.ahead_pts)}</Num></span>, trust: <TrustCell t={r.trust} />,
  }));
  const t = h.total;
  const total = { pf: <strong>All {t.count} portfolios</strong>, value: t.value === null ? NOT_YET : <strong><Num>{money(t.value)}</Num></strong>, pnl: t.pnl === null ? <Dash /> : <strong><Num>{signed(t.pnl)}</Num></strong>,
    ret: "", vs: "", trust: t.unexplained === null ? "" : <span className="ds-muted">Unexplained {Number(t.unexplained) === 0 ? "0" : money(t.unexplained)}</span> };
  const entityRows = h.entities.map((e) => ({
    en: <>{e.entity}<div className="ds-muted" style={{ fontSize: "0.85rem" }}>{e.portfolios} portfolio{e.portfolios === 1 ? "" : "s"}</div><WhereLink label={e.entity} where={e.where} id={e.trail_id} /></>,
    value: e.value === null ? NOT_YET : <Num>{money(e.value)}</Num>, pnl: signedOrDash(e.pnl), trust: <TrustCell t={e.trust} />,
  }));
  return (
    <PageFrame title="Financial health" subline="The detail behind today's numbers: each portfolio, each entity and each fund, with how much we trust each value.">
      <div role="group" aria-label="Level of detail" style={{ display: "flex", gap: 8, flexWrap: "wrap", margin: "0 0 14px" }}>
        {LEVELS.map(([id, text]) => <Chip key={id} tone={level === id ? "active" : "default"} onClick={() => setLevel(id)}>{text}</Chip>)}
      </div>
      {level === "portfolio" ? (
        <section aria-label="By portfolio">
          {h.portfolios.length === 0 ? <p className="ds-muted">Nothing you can see is valued yet.</p> : (
            <DataTable columns={[{ key: "pf", label: "Portfolio" }, { key: "value", label: `Value, ${h.currency}` }, { key: "pnl", label: `P&L, ${h.period.month}` }, { key: "ret", label: "Return" }, { key: "vs", label: "vs bench, pts" }, { key: "trust", label: "Trust in the value" }]}
              rows={[...portfolioRows, total]} />)}
        </section>
      ) : level === "entity" ? (
        <section aria-label="By entity">
          {h.entities.length === 0 ? <p className="ds-muted">Nothing you can see is valued yet.</p> : (
            <DataTable columns={[{ key: "en", label: "Entity" }, { key: "value", label: `Value, ${h.currency}` }, { key: "pnl", label: `P&L, ${h.period.month}` }, { key: "trust", label: "Trust in the value" }]}
              rows={[...entityRows, { en: <strong>All {h.entities.length} entities</strong>, value: t.value === null ? NOT_YET : <strong><Num>{money(t.value)}</Num></strong>, pnl: t.pnl === null ? <Dash /> : <strong><Num>{signed(t.pnl)}</Num></strong>, trust: "" }]} />)}
        </section>
      ) : (
        <section aria-label="By fund">
          <FundLeague embedded />
          <IndexMapPanel />
        </section>
      )}
      <section aria-label="Funds needing attention" style={{ marginTop: 16 }}>
        <StatGrid cols={3}>
          <StatCard label="Funds on official values" value={`${f.official} of ${f.total}`} note={f.revised ? `Plus ${f.revised} revised to final` : undefined} />
          <StatCard label="On estimates" value={String(f.estimated)} note={f.estimated_who || undefined} />
          <StatCard label="Old or unconfirmed" value={String(f.old)} tone="warn" note={f.old_who || undefined} />
        </StatGrid>
      </section>
      <Footnote>Each row opens to where its number came from. "By fund" is the fund league: each fund against the index that fits it. Values still on an estimate or not confirmed carry their status word.</Footnote>
      <div style={{ marginTop: 16 }}><AskLumen /></div>
    </PageFrame>
  );
}
