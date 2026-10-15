import { Link } from "react-router-dom";
import { useEffect, useState, type FormEvent, type ReactNode } from "react";

import { apiSend, getCompany } from "../api/client";
import { getCatalogue, getEgressLog, getProviders, getSettings, listCompanies, setCentre, setEgress, setEmailDomains, setModule } from "../api/control";
import type { ControlCompany, EgressKey } from "../api/control";
import { useLoad, type Loaded } from "../components/useLoad";
import ScreenState from "../components/ScreenState";
import { Button, DataTable, EmptyState, Footnote, PageFrame, Pill, SideCard } from "../design";
import { useSession } from "../useSession";
import { controlText as t, NA, pack } from "./controlCopy";

// Page-only layout; every colour is a design token.
const style = `
.ds-frame__main, .ds-frame__rail { min-width: 0; max-width: 100%; }
.cp-card { padding: 16px 18px; display: flex; flex-direction: column; gap: 4px; }
.cp-card h2 { margin: 0 0 4px; font-size: 16px; }
.cp-card h3 { margin: 12px 0 2px; font-size: 12px; letter-spacing: 1.5px; text-transform: uppercase; color: var(--ds-ink-muted); font-weight: 600; }
.cp-head { margin: 0; font-size: 14px; color: var(--ds-ink-soft); }
.cp-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; min-height: 44px; border-bottom: 1px solid var(--ds-line); font-size: 14px; }
.cp-row:last-child { border-bottom: 0; }
.cp-row__name { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.cp-row__name small { color: var(--ds-ink-muted); font-size: 12px; }
.ds-screen input.cp-switch[type="checkbox"] { appearance: none; flex: none; width: 40px; min-width: 40px; min-height: 22px; height: 22px; border-radius: 999px; background: var(--ds-line-2); position: relative; cursor: pointer; margin: 0; }
.cp-switch::after { content: ""; position: absolute; top: 3px; left: 3px; width: 16px; height: 16px; border-radius: 50%; background: var(--ds-ink); transition: left .15s ease; }
.ds-screen input.cp-switch:checked { background: var(--ds-teal); }
.cp-switch:checked::after { left: 21px; }
.ds-screen input.cp-switch:disabled { opacity: .6; cursor: not-allowed; }
.cp-switch:focus-visible { outline: 2px solid var(--ds-teal-bright); outline-offset: 2px; }
.cp-form { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)) auto; gap: 10px; align-items: end; }
.cp-form label { display: flex; flex-direction: column; gap: 4px; font-size: 12px; color: var(--ds-ink-muted); }
.cp-form input { min-height: 40px; box-sizing: border-box; padding: 8px 10px; border-radius: 8px; border: 1px solid var(--ds-line-2); background: var(--ds-ground); color: var(--ds-ink); font: inherit; font-size: 14px; }
.cp-form input:focus-visible { outline: 2px solid var(--ds-teal-bright); outline-offset: 1px; }
.cp-alert { margin: 0; color: var(--ds-amber); font-size: 13px; }
.cp-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; align-items: start; }
.cp-pill { font-family: var(--ds-mono, ui-monospace, monospace); font-size: 11px; padding: 2px 7px; border-radius: 4px; background: var(--ds-line); color: var(--ds-ink-soft); }
.cp-dom { display: flex; flex-direction: column; gap: 6px; padding-top: 10px; font-size: 13px; }
.cp-dom input { min-height: 40px; box-sizing: border-box; padding: 8px 10px; border-radius: 8px; border: 1px solid var(--ds-line-2); background: var(--ds-ground); color: var(--ds-ink); font: inherit; font-size: 14px; }
.cp-dom small { color: var(--ds-ink-muted); font-size: 12px; }
.cp-pick { display: flex; flex-direction: column; gap: 4px; font-size: 12px; color: var(--ds-ink-muted); max-width: 320px; }
.cp-pick select { min-height: 40px; padding: 8px 10px; border-radius: 8px; border: 1px solid var(--ds-line-2); background: var(--ds-ground); color: var(--ds-ink); font: inherit; font-size: 14px; }
.cp-side p { margin: 0; font-size: 13px; color: var(--ds-ink-soft); }
@media (max-width: 900px) { .cp-grid { grid-template-columns: 1fr; } }
@media (max-width: 700px) { .cp-form { grid-template-columns: 1fr; } }
`;

function Switch({ label, name, note, on, disabled, onChange }: {
  label: string; name: ReactNode; note?: string; on: boolean; disabled?: boolean; onChange?: (v: boolean) => void;
}) {
  return (
    <label className="cp-row">
      <span className="cp-row__name"><span>{name}</span>{note ? <small>{note}</small> : null}</span>
      <input className="cp-switch" type="checkbox" role="switch" aria-label={label} checked={on} disabled={disabled} onChange={(e) => onChange?.(e.target.checked)} />
    </label>
  );
}

function Card({ title, children }: { title?: string; children: ReactNode }) {
  return <section className="ds-card cp-card">{title ? <h2>{title}</h2> : null}{children}</section>;
}

/** Super admin: the companies and the form that creates one. */
function Companies({ rows, onCreated }: { rows: ControlCompany[]; onCreated: () => void }) {
  const [form, setForm] = useState({ id: "", display: "", industry: "" });
  const [busy, setBusy] = useState(false);
  const [bad, setBad] = useState<string | null>(null);
  const packs = [...new Set(rows.map((c) => c.industry).filter((x): x is string => !!x))];
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      await apiSend("POST", "/api/control/companies", form);
      setForm({ id: "", display: "", industry: "" });
      setBad(null);
      onCreated();
    } catch (err) {
      setBad(err instanceof Error && err.message ? err.message : t.create.failed);
    } finally {
      setBusy(false);
    }
  };
  const field = (k: keyof typeof form, label: string, extra?: object) => (
    <label>{label}<input required value={form[k]} onChange={(e) => setForm({ ...form, [k]: e.target.value })} {...extra} /></label>
  );
  return (
    <>
      {rows.length === 0 ? <EmptyState title={t.centres.none} lines={[t.centres.noneLine]} /> : (
        <DataTable columns={[...t.companies.cols]} rows={rows.map((c) => ({
          name: c.display ?? c.id,
          pack: c.industry ? pack(c.industry) : NA,
          accounts: t.brand.accounts(c.accounts.active, c.accounts.total),
          on: c.centres_on.length ? c.centres_on.join(", ") : "None",
        }))} />
      )}
      <Card title={t.create.title}>
        <form className="cp-form" onSubmit={(e) => void submit(e)}>
          {field("id", t.create.id)}
          {field("display", t.create.display)}
          {field("industry", t.create.industry, { list: "cp-packs" })}
          <datalist id="cp-packs">{packs.map((p) => <option key={p} value={p} />)}</datalist>
          <Button type="submit" variant="primary" disabled={busy}>{busy ? t.create.busy : t.create.button}</Button>
        </form>
        {bad ? <p role="alert" className="cp-alert">{bad}</p> : null}
        <Footnote>{t.create.note}</Footnote>
      </Card>
    </>
  );
}

/** Super admin: one switch per centre and module, per company, under the company header. */
function SuperCentres({ rows }: { rows: ControlCompany[] }) {
  const cat = useLoad(getCatalogue, "cat");
  const [on, setOn] = useState<Record<string, boolean>>({});
  const [bad, setBad] = useState(false);
  const [sel, setSel] = useState("ardmore");
  const [saved, setSaved] = useState("");
  useEffect(() => {
    const m: Record<string, boolean> = {};
    rows.forEach((c) => {
      c.centres_on.forEach((x) => (m[`${c.id}/centres/${x}`] = true));
      c.modules_on.forEach((x) => (m[`${c.id}/modules/${x}`] = true));
    });
    setOn(m);
  }, [rows]);
  const flip = async (cid: string, kind: "centres" | "modules", id: string, v: boolean) => {
    try {
      await (kind === "centres" ? setCentre : setModule)(cid, id, v);
      setOn((o) => ({ ...o, [`${cid}/${kind}/${id}`]: v }));
      setSaved(`${cid}/${kind}/${id}`);
      setBad(false);
    } catch {
      setBad(true);
    }
  };
  return (
    <>
      <ScreenState state={cat.state} message={cat.message} onRetry={cat.retry}>
        {bad ? <p role="alert" className="cp-alert">{t.leave.failed}</p> : null}
        <label className="cp-pick">{t.centres.pick}
          <select value={rows.some((c) => c.id === sel) ? sel : rows[0]?.id ?? ""} onChange={(e) => { setSel(e.target.value); setSaved(""); }}>
            {rows.map((c) => <option key={c.id} value={c.id}>{c.display ?? c.id}</option>)}
          </select>
        </label>
        {rows.filter((c) => c.id === (rows.some((r) => r.id === sel) ? sel : rows[0]?.id)).map((c) => {
          const lit = (cat.data?.centres ?? []).filter((x) => on[`${c.id}/centres/${x.id}`]).map((x) => x.name);
          return (
            <Card key={c.id} title={`${t.centres.title}: ${c.display ?? c.id}`}>
              <p className="cp-head">{t.header(c.display ?? c.id, c.industry, c.accounts.total, lit)} {t.nextRequest}</p>
              <h3>{t.centres.centres}</h3>
              {cat.data?.centres.map((x) => (
                <Switch key={x.id} label={`${c.id} ${x.name}`} name={x.name} note={saved === `${c.id}/centres/${x.id}` ? t.saved : x.description} on={!!on[`${c.id}/centres/${x.id}`]}
                  onChange={(v) => void flip(c.id, "centres", x.id, v)} />
              ))}
              <h3>{t.domains.label}</h3>
              <p className="cp-head">{(c.email_domains ?? []).length ? (c.email_domains ?? []).join(", ") : t.domains.none}</p>
              <h3>{t.centres.modules}</h3>
              {cat.data?.modules.map((x) => (
                <Switch key={x.id} label={`${c.id} ${x.id}`} name={<><Pill tone="open">{`M${x.number}`}</Pill> {x.name}</>} note={saved === `${c.id}/modules/${x.id}` ? t.saved : undefined} on={!!on[`${c.id}/modules/${x.id}`]}
                  onChange={(v) => void flip(c.id, "modules", x.id, v)} />
              ))}
            </Card>
          );
        })}
      </ScreenState>
      <Footnote>{t.centres.offRule}</Footnote>
    </>
  );
}

function Catalogue() {
  const l = useLoad(getCatalogue, "cat2");
  return (
    <ScreenState state={l.state} message={l.message} onRetry={l.retry}>
      <DataTable columns={[{ key: "id", label: "Module" }, { key: "name", label: "Name" }, { key: "agent", label: "Agent" }]}
        rows={(l.data?.modules ?? []).map((m) => ({ id: <Pill tone="open">{`M${m.number}`}</Pill>, name: m.name, agent: m.agent }))} />
    </ScreenState>
  );
}

function Providers() {
  const l = useLoad(getProviders, "prov");
  return (
    <ScreenState state={l.state} message={l.message} onRetry={l.retry}>
      <DataTable columns={[{ key: "company", label: "Company" }, { key: "provider", label: "Provider and model" }]}
        rows={Object.entries(l.data?.companies ?? {}).map(([cid, p]) => ({ company: cid, provider: p ? `${p.provider} ${p.model}` : t.providers.unset }))} />
    </ScreenState>
  );
}

function Stub({ note }: { note: string }) {
  return <EmptyState title={NA} lines={[note]} />;
}

function Leave({ title }: { title?: string }) {
  const l = useLoad(getSettings, "settings");
  const [egress, setE] = useState<{ internet: boolean; connectors: boolean; cloud_push_requested: boolean } | null>(null);
  const [bad, setBad] = useState(false);
  const [domains, setDomains] = useState("");
  const [note, setNote] = useState<string | null>(null);
  useEffect(() => { if (l.data) { setE(l.data.egress); setDomains((l.data.email_domains ?? []).join(", ")); } }, [l.data]);
  const flip = async (k: EgressKey, v: boolean) => {
    try {
      setE((await setEgress(k, v)).egress);
      setBad(false);
    } catch {
      setBad(true);
    }
  };
  const saveDomains = async (e: FormEvent) => {
    e.preventDefault();
    try {
      const r = await setEmailDomains(domains.split(",").map((d) => d.trim()).filter(Boolean));
      setDomains(r.email_domains.join(", "));
      setNote(t.domains.saved);
    } catch {
      setNote(t.domains.failed);
    }
  };
  return (
    <ScreenState state={l.state} message={l.message} onRetry={l.retry}>
      <Card title={title}>
        <Switch label={t.leave.rows.gateway} name={t.leave.rows.gateway} note={t.leave.gatewayNote} on disabled />
        <Switch label={t.leave.rows.internet} name={t.leave.rows.internet} on={!!egress?.internet} onChange={(v) => void flip("internet", v)} />
        <Switch label={t.leave.rows.connectors} name={t.leave.rows.connectors} on={!!egress?.connectors} onChange={(v) => void flip("connectors", v)} />
        <Switch label={t.leave.rows.cloud_push} name={t.leave.rows.cloud_push}
          note={`${t.leave.cloudNote}${egress?.cloud_push_requested ? ` (${t.leave.requested})` : ""}`}
          on={!!egress?.cloud_push_requested} onChange={(v) => void flip("cloud_push", v)} />
        <form className="cp-dom" onSubmit={(e) => void saveDomains(e)}>
          <label htmlFor="cp-domains">{t.domains.label}</label>
          <input id="cp-domains" value={domains} onChange={(e) => { setDomains(e.target.value); setNote(null); }} />
          <small>{t.domains.hint}</small>
          <div><Button type="submit" variant="primary">{t.domains.save}</Button></div>
          {note ? <p role="status" className="cp-alert">{note}</p> : null}
        </form>
        {bad ? <p role="alert" className="cp-alert">{t.leave.failed}</p> : null}
      </Card>
    </ScreenState>
  );
}

function CompanyCentres({ settings, name }: { settings: Loaded<Awaited<ReturnType<typeof getSettings>>>; name: string | null }) {
  const on = settings.data?.centres ?? [];
  return (
    <>
      <div className="cp-grid">
        <Card title={t.centres.title}>
          <ScreenState state={settings.state} message={settings.message} onRetry={settings.retry}>
            {Object.keys(t.centreMods).map((c) => (
              <Switch key={c} label={c} name={<>{pack(c)} centre <span className="cp-pill">{t.centreMods[c]}</span></>} on={on.includes(c)} disabled />
            ))}
          </ScreenState>
          <Footnote>{t.centres.offRule}</Footnote>
        </Card>
        <Leave title={t.leave.title} />
        <Card title={t.agents.title}>
          {t.agents.rows.map((a) => (
            <div className="cp-row" key={a.name}>
              <span><strong>{a.name}</strong> · {a.role} <span className="cp-pill">{a.tag}</span></span>
              <small>{a.reads}</small>
            </div>
          ))}
        </Card>
        <Card title={t.brand.title}>
          <div className="cp-row"><span>{t.brandRows.logo}</span><span>{name ?? NA}</span></div>
          <div className="cp-row"><span>{t.brandRows.accounts}</span><span>{NA}</span></div>
          <div className="cp-row"><span>{t.brandRows.linked}</span><span>{NA}</span></div>
          <div className="cp-row"><span>{t.brandRows.restricted}</span><span>{NA}</span></div>
        </Card>
      </div>
      <Card title={t.logLast}><Log limit={5} /></Card>
    </>
  );
}

function Log({ limit = 50 }: { limit?: number }) {
  const l = useLoad(() => getEgressLog(limit), `log${limit}`, (d) => d.entries.length === 0);
  const keys = ["time", "module", "kind", "host", "decision", "bytes"] as const;
  const when = (v: string | null) => {
    const d = v ? new Date(v) : null;
    return d && !Number.isNaN(d.getTime()) ? d.toLocaleString("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", second: "2-digit" }) : NA;
  };
  return (
    <>
      {l.state === "empty" ? <EmptyState title={t.log.empty} lines={[]} /> : (
        <ScreenState state={l.state} message={l.message} onRetry={l.retry}>
          <DataTable columns={keys.map((k, i) => ({ key: k, label: t.log.cols[i] ?? k }))}
            rows={(l.data?.entries ?? []).map((e) => ({ ...Object.fromEntries(keys.map((k) => [k, e[k] ?? ""])), time: when(e.time), decision: [e.decision, e.reason_code].filter(Boolean).join(" · ") }))} />
        </ScreenState>
      )}
      <Footnote>{t.log.note}</Footnote>
    </>
  );
}

/** The company admin's header line: their own company only, from the routes they may call. */
function useOwnHeader(on: boolean, settings: Loaded<Awaited<ReturnType<typeof getSettings>>>): { line: string; name: string } | null {
  const co = useLoad(async () => (on ? getCompany() : null), on ? "own-company" : "no-company");
  if (!on || !co.data) return null;
  return { line: t.header(co.data.name, co.data.industry, null, settings.data?.centres ?? []), name: co.data.name };
}

export default function ControlPage() {
  const { user } = useSession();
  const isSuper = !!user?.roles.includes("super_admin");
  const isAdmin = !!user?.roles.includes("company_admin");
  const [active, setActive] = useState<string>(isSuper ? "companies" : "centres");
  // each role calls only its own routes: /api/control/* is super admin only, /api/company/settings company admin only
  const companies = useLoad(async () => (isSuper ? (await listCompanies()).companies : []), isSuper ? "companies" : "no-companies");
  const settings = useLoad(async () => (isAdmin ? getSettings() : { email_domains: [], centres: [], egress: { internet: false, connectors: false, cloud_push: false, cloud_push_requested: false } }), isAdmin ? "settings2" : "no-settings");
  const own = useOwnHeader(isAdmin, settings);
  const header = own?.line ?? null;
  const ownName = own?.name ?? null;
  if (!isSuper && !isAdmin) return <ScreenState state="refused" message={t.refused} />;

  const group = (label: string, items: readonly { id: string; label: string }[]) => (
    <>
      <p className="ds-rail__group">{label}</p>
      {items.map((i) => (
        <button type="button" key={i.id} className="ds-rail__item" aria-current={active === i.id} onClick={() => setActive(i.id)}>{i.label}</button>
      ))}
    </>
  );
  const withCompanies = (render: (rows: ControlCompany[]) => ReactNode) => (
    <ScreenState state={companies.state} message={companies.message} onRetry={companies.retry}>{render(companies.data ?? [])}</ScreenState>
  );
  const sections: Record<string, { title: string; body: () => ReactNode }> = {
    companies: { title: t.companies.title, body: () => withCompanies((r) => <><Companies rows={r} onCreated={companies.retry} /><SuperCentres rows={r} /></>) },
    packs: { title: t.packs.title, body: () => <Stub note={t.packs.note} /> },
    catalogue: { title: t.catalogue.title, body: () => <Catalogue /> },
    agents: { title: t.agentsModels.title, body: () => <Stub note={t.agentsModels.note} /> },
    providers: { title: t.providers.title, body: () => <Providers /> },
    brand: { title: t.brand.title, body: () => <Card><p className="cp-head">{header ?? NA}</p><Footnote>{NA}</Footnote></Card> },
    centres: { title: t.centres.title, body: () => <CompanyCentres settings={settings} name={ownName} /> },
    leave: { title: t.leave.title, body: () => <Leave /> },
    retention: { title: t.retention.title, body: () => <Stub note={t.retention.note} /> },
    log: { title: t.log.title, body: () => <Log /> },
  };
  const section = sections[active] ?? sections.log!;

  return (
    <div className="ds-screen">
      <style>{style}</style>
      <PageFrame
        title={t.title}
        subline={<Pill tone="restricted">{t.banner}</Pill>}
        rail={
          <nav aria-label={t.rail}>
            {isSuper ? group(t.groups.plane, t.planeNav) : null}
            {isAdmin ? group(t.groups.company, t.companyNav) : null}
            {isSuper ? (
              <p className="ds-rail__group">
                <Link className="ds-rail__item" to="/centre/control/intents">Intents</Link>
              </p>
            ) : null}
          </nav>
        }
        aside={
          <>
            <SideCard title={t.roles.title}>
              <div className="cp-side">{t.roles.rows.map((r) => <p key={r.role}><strong>{r.role}</strong> {r.can}</p>)}</div>
            </SideCard>
            <SideCard title={t.planes.title}>
              <div className="cp-side">{t.planes.rows.map((r) => <p key={r.name}><strong>{r.name}</strong> {r.note}</p>)}</div>
            </SideCard>
            <SideCard title={t.notBuilt.title}>
              <div className="cp-side">{t.notBuilt.rows.map((r) => <p key={r}><Pill tone="late">{NA}</Pill> {r}</p>)}</div>
            </SideCard>
          </>
        }
      >
        {header ? <p className="cp-head">{header} {t.nextRequest}</p> : null}
        <h2 className="ds-strip__label ds-muted">{section.title}</h2>
        {section.body()}
      </PageFrame>
    </div>
  );
}
