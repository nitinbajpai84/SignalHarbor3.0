import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import Panel from "../../components/Panel";
import ScreenState from "../../components/ScreenState";
import { Button, Chip } from "../../design";
import { OutcomeBody } from "./OutcomeCard";
import { converge, useConverge, when, type Loaded, type Row, type View } from "./convergeApi";
import { t } from "./convergeCopy";
import "./converge.css";

type Filter = "all" | "groups" | "cards";
const flat = (rows: Row[]): Row[] => rows.flatMap((r) => [r, ...(r.cards ?? [])]);

function BackedBar({ n, max }: { n: number; max: number }) {
  return <span className="cv-bar" aria-hidden="true"><span style={{ width: `${max ? Math.round((n / max) * 100) : 0}%` }} /></span>;
}

function RowView({ row, v, l, max, nested = false }: { row: Row; v: View; l: Loaded; max: number; nested?: boolean }) {
  const [open, setOpen] = useState(false);
  const cap = v.converge.max_backs ?? 3;
  const full = !row.i_backed && (v.converge.used ?? 0) >= cap;
  const reason = v.converge.state === "not_open" ? t.notOpen : !["round_1_open", "round_2_open"].includes(v.converge.state) ? t.closed : "";
  return (
    <li className={`cv-row${nested ? " cv-row--nested" : ""}${row.i_backed ? " cv-row--mine" : ""}`}>
      <div className="cv-row__main">
        <strong className="cv-row__text">{row.text}</strong>
        {row.kind === "group" ? (
          <span className="cv-row__meta">{t.ideas(row.note_count ?? 0)}{row.samples?.length ? `: ${row.samples.join("; ")}` : ""}</span>
        ) : row.from ? <span className="cv-row__meta">{row.from}</span> : null}
        <span className="cv-row__chips">
          <Chip>{t.backedCount(row.backed)}</Chip>
          {row.i_backed && <Chip tone="active">{t.youBacked}</Chip>}
          {row.tie ? <Chip>{t.tie(row.tie)}</Chip> : null}
          {row.top ? <Chip>{t.top}</Chip> : null}
        </span>
        <BackedBar n={row.backed} max={max} />
      </div>
      <div className="cv-row__acts">
        {v.viewer.seated && (
          <Button variant={row.i_backed ? "primary" : "secondary"} aria-pressed={row.i_backed} disabled={l.busy || !!reason}
            title={reason || (full ? t.noBacks(cap) : undefined)}
            onClick={() => l.run(() => converge.back(v.id, row.ref, !row.i_backed))}>
            {row.i_backed ? t.backed : t.backThis}
          </Button>
        )}
        {row.cards?.length ? <Button onClick={() => setOpen(!open)} aria-expanded={open}>{open ? t.hideIdeas : t.showIdeas}</Button> : null}
      </div>
      {open && row.cards && <ul className="cv-list cv-list--inner">{row.cards.map((c) => <RowView key={c.ref} row={c} v={v} l={l} max={max} nested />)}</ul>}
    </li>
  );
}

function YourBacks({ v, l }: { v: View; l: Loaded }) {
  const max = v.converge.max_backs ?? 3;
  const live = ["round_1_open", "round_2_open"].includes(v.converge.state);
  return (
    <Panel title={t.yourBacks} className="cv-yourbacks">
      <p className="cv-used">{t.used(v.converge.used ?? 0, max)}</p>
      {v.mine.length === 0 ? <p className="ds-muted">{t.noBacks(max)}</p> : (
        <ul className="cv-mine">{v.mine.map((m) => (
          <li key={m.ref}><span>{m.text}</span>{live && <Button disabled={l.busy} onClick={() => l.run(() => converge.back(v.id, m.ref, false))}>{t.takeBack}</Button>}</li>
        ))}</ul>
      )}
    </Panel>
  );
}

function OrganiserPanel({ v, l, intentId }: { v: View; l: Loaded; intentId: string }) {
  const [, setParams] = useSearchParams();
  const [asking, setAsking] = useState(false);
  const [picks, setPicks] = useState<string[]>([]);
  const st = v.converge.state;
  const live = st === "round_1_open" || st === "round_2_open";
  const closedRound = st === "round_1_closed" || st === "round_2_closed";
  const text = new Map(flat(v.rows).map((r) => [r.ref, r.text]));
  const tie = v.tie && !v.tie.resolved ? v.tie : null;
  return (
    <Panel title={t.organiserTitle} className="cv-org">
      {st === "not_open" && <Button variant="primary" disabled={l.busy} onClick={() => l.run(() => converge.open(intentId))}>{t.openCount}</Button>}
      {live && (
        <>
          <Button variant="primary" disabled={l.busy || !!v.can.close} onClick={() => setAsking(true)}>{t.closeCount}</Button>
          {v.can.close && <p className="ds-muted cv-why">{v.can.close}</p>}
          {asking && (
            <div role="dialog" aria-modal="true" aria-label={t.closeCount} className="cv-dialog">
              <p>{t.closeAsk(v.have_backed, v.seated_count)}</p>
              <div className="cv-dialog__acts">
                <Button variant="primary" disabled={l.busy} onClick={async () => { if (await l.run(() => converge.close(intentId))) setAsking(false); }}>{t.confirm}</Button>
                <Button onClick={() => setAsking(false)}>{t.cancel}</Button>
              </div>
            </div>
          )}
        </>
      )}
      {tie && (
        <div role="dialog" aria-modal="true" aria-label="Tied ideas" className="cv-dialog">
          <p>{t.tieTitle(tie.among.map((r) => text.get(r) ?? "").join(", "), tie.free)}</p>
          {tie.among.map((r) => (
            <label key={r} className="cv-check">
              <input type="checkbox" checked={picks.includes(r)} onChange={(e) => setPicks(e.target.checked ? [...picks, r] : picks.filter((x) => x !== r))} />
              {text.get(r)}
            </label>
          ))}
          <p className="ds-muted">{t.tiePick(tie.free)}</p>
          <Button variant="primary" disabled={l.busy || picks.length !== tie.free} onClick={() => l.run(() => converge.close(intentId, picks))}>{t.useThese}</Button>
        </div>
      )}
      {closedRound && v.converge.round !== 2 && (
        <>
          <Button disabled={l.busy || !!v.can.round2} onClick={() => l.run(() => converge.round2(intentId))}>{t.round2}</Button>
          {v.can.round2 && <p className="ds-muted cv-why">{v.can.round2}</p>}
        </>
      )}
      {closedRound && <Button disabled={!!tie} onClick={() => setParams({ view: "outcome" })}>{t.skip}</Button>}
      <Link className="ds-btn" to={`/centre/intent/${intentId}/close`}>{t.closeWhatWeHave}</Link>
    </Panel>
  );
}

/** Screen A of spec 37 (and, with `?view=outcome` or once confirmed, Screen B). B20's session view mounts it as <Converge intentId={id} />. */
export default function Converge({ intentId }: { intentId: string }) {
  const l = useConverge(intentId);
  const [params, setParams] = useSearchParams();
  const [filter, setFilter] = useState<Filter>("all");
  const v = l.view;
  if (l.failed) return <ScreenState state="error" message={t.failed} onRetry={l.reload} />;
  if (!v) return <ScreenState state="loading" message={t.loading} />;
  const st = v.converge.state;
  if (params.get("view") === "outcome" || st === "done" || v.tier !== "content") {
    return <OutcomeBody l={l} intentId={intentId} back={st === "done" || v.tier !== "content" ? undefined : () => setParams({})} />;
  }
  const rows = filter === "groups" ? v.rows.filter((r) => r.kind === "group") : filter === "cards" ? flat(v.rows).filter((r) => r.kind === "card") : v.rows;
  const max = Math.max(0, ...flat(v.rows).map((r) => r.backed));
  const live = st === "round_1_open" || st === "round_2_open";
  const none = v.rows.length === 0;
  return (
    <div className="cv ic-phone">
      <header className="cv-head">
        <Chip>{t.choosing}</Chip>
        {st !== "not_open" && <Chip tone="active">{t.round(v.converge.round)}</Chip>}
        {v.converge.round ? <span className="ds-muted">{t.roundLine(v.converge.round, v.converge.max_rounds ?? 2)}</span> : null}
        {v.ends && <span className="ds-muted">{t.ends(when(v.ends, v.tz))}</span>}
      </header>
      {l.notice && <p role="alert" className="state state-error">{l.notice}</p>}
      {v.viewer.seated && live && <div className="cv-strip" aria-live="polite">{t.used(v.converge.used ?? 0, v.converge.max_backs ?? 3)}</div>}
      <div className="cv-grid">
        <section className="cv-main" aria-label="Ideas to back">
          <div className="cv-filters" role="group" aria-label="Filter">
            {(["all", "groups", "cards"] as Filter[]).map((f) => <Chip key={f} tone={filter === f ? "active" : "default"} onClick={() => setFilter(f)}>{t.filters[f]}</Chip>)}
          </div>
          {st === "not_open" && <p className="ds-muted">{t.notOpen}</p>}
          {none ? <p className="ds-muted">{t.noIdeas}</p> : (
            <ul className="cv-list">{rows.map((r) => <RowView key={r.ref} row={r} v={v} l={l} max={max} />)}</ul>
          )}
        </section>
        <aside className="cv-side">
          {v.viewer.seated && <YourBacks v={v} l={l} />}
          {v.viewer.organiser && <OrganiserPanel v={v} l={l} intentId={intentId} />}
          <Panel title={t.nira} className="cv-north">
            <p>{v.north || t.waitingFirst}</p>
            {live && !v.have_backed && <p className="ds-muted">{t.none}</p>}
          </Panel>
        </aside>
      </div>
    </div>
  );
}
