import { useEffect, useState, type ReactNode } from "react";
import { useParams, useSearchParams } from "react-router-dom";

import { ApiError, apiSend } from "../api/client";
import { useLoad } from "../components/useLoad";
import { Button, Chip, DataTable, EmptyState, Footnote, PageFrame, Pill, SideCard, StatCard, StatGrid, type PillTone } from "../design";
import { useSession } from "../useSession";
import { CHANGED, ROLES, confirmPart, getGoverned, getMyParts, getProcessMap, getWorkList, notifyChanged, putTriage, type GovernedView, type Kpi, type KpiFull, type KpiMap, type MyParts, type Prov, type ProcessMap, type WorkList } from "../modules/m2_baseline/api";
import { m2Signoff, m2Work } from "../modules/m2_baseline/copy";
import { getGlossary, reviewEntry, type GlossaryEntry } from "../modules/m2_baseline/glossary/glossaryApi";
import KpiMapPanel from "../modules/m2_baseline/process_map/KpiMapPanel";
import KpiDetail from "../modules/m2_baseline/worklist/KpiDetail";
import BaselineSignoff from "./BaselineSignoff";

type Filter = "all" | "must" | "should" | "mine";
const FILTERS: [Filter, string][] = [["all", "All"], ["must", "Must"], ["should", "Should"], ["mine", "Mine"]];
const MARK = { stated: "Stated", guessed: "Guessed", unknown: "Not known yet" } as const;
const OWNER = { business: "Business owner", data: "Data owner", process: "Process owner" } as const;
type Field = "definition" | "producer" | "gathered";
const COLUMN = { display: "flex", flexDirection: "column", gap: 16 } as const;
const LINK_BUTTON = { background: "none", border: 0, padding: 0, font: "inherit", cursor: "pointer", textAlign: "left" } as const;
const FIELD: Record<string, string> = { owners: "Owners", classification: "Class", may_see: "Seen by", resolving: "Resolved by", affects: "Affects", review_date: "Review date" };
const NOT_YET = "Not available yet";

/** A governed cell's value in words, from the record only: owners by role, the resolving team and its target week, a list joined.
 * A stated empty list is a decision ("Everyone in the company" for who may see, "None recorded" otherwise); nothing at all is "Not available yet". */
const words = (field: string, v: unknown): string => {
  if (v == null || v === "") return NOT_YET;
  if (Array.isArray(v)) return v.length ? v.map(String).join(", ") : field === "may_see" ? "Everyone in the company" : "None recorded";
  if (typeof v !== "object") return String(v);
  const o = v as Record<string, unknown>;
  if (field === "resolving") return [o.team, o.target_week != null ? `by week ${String(o.target_week)}` : ""].filter(Boolean).join(", ") || NOT_YET;
  const label = (k: string) => (k in OWNER ? OWNER[k as keyof typeof OWNER].replace(" owner", "") : k);
  return Object.entries(o).filter(([, x]) => x != null && x !== "").map(([k, x]) => `${label(k)}: ${String(x)}`).join(" · ") || NOT_YET;
};

/** Status words for the list: governed = signed off; confirmed = a person has stated the definition; otherwise Lens drafted it. */
const statusOf = (k: KpiFull): [string, PillTone] =>
  k.state === "signed" ? ["Governed", "signed"] : k.triage.definition.mark === "stated" ? ["Confirmed", "ok"] : ["Drafted by Lens", "draft"];

const plain = (e: unknown) => (e instanceof ApiError && e.message ? e.message : m2Work.saveFailed);

/** The artboard's provenance line: "Guessed · by Lens · from the fee schedule". Unknown shows only its mark, never words. */
function ProvLine({ p }: { p: Prov }) {
  const known = p.mark !== "unknown";
  return <Footnote>{[MARK[p.mark], known && p.by ? m2Work.by(p.by) : "", known && p.from ? m2Work.fromWhere(p.from) : ""].filter(Boolean).join(" · ")}</Footnote>;
}

/** One labelled value with its provenance line, and Confirm when Lens guessed it. */
function Value({ label, p, confirm }: { label: string; p: Prov; confirm?: ReactNode }) {
  return (
    <div>
      <Footnote>{label}</Footnote>
      {p.value ? <p>{p.value}</p> : null}
      <ProvLine p={p} />
      {p.mark === "guessed" && p.value ? confirm : null}
    </div>
  );
}

/** The artboard's governed-state panel: six fields from the governed record. The count is the record's stated fields (6 minus `missing`);
 * a guess is shown with its mark, never counted as governed. */
function GovernedState({ gov, kpiId, onConfirm }: { gov: GovernedView | null; kpiId: string; onConfirm?: (field: string, value: unknown) => void }) {
  const measure = gov?.measures.find((m) => m.id === kpiId);
  if (!measure) return null;
  const entries = Object.entries(measure.state);
  const stated = entries.length - measure.missing.length;
  const guessed = entries.filter(([, c]) => c.mark === "guessed");
  return (
    <SideCard title={`${measure.name ? `${measure.name} · ` : ""}Governed state · ${stated} of ${entries.length}`} tone={measure.governed ? "teal" : "amber"}>
      <StatGrid cols={2}>
        {entries.map(([key, cell]) => {
          const value = cell.mark === "unknown" ? NOT_YET : words(key, cell.value);
          return <StatCard key={key} bare text label={FIELD[key] ?? key} value={value} valueTone={cell.mark === "stated" ? undefined : "warn"} note={cell.mark === "stated" ? undefined : MARK[cell.mark]} tone="muted" />;
        })}
      </StatGrid>
      {onConfirm && guessed.length ? (
        <div className="ds-frame__actions">
          {guessed.map(([key, c]) => <Button key={key} onClick={() => onConfirm(key, c.value)}>{`Confirm ${(FIELD[key] ?? key).toLowerCase()}`}</Button>)}
        </div>
      ) : null}
    </SideCard>
  );
}

/** A person whose role cannot open the whole work list (owner, approver, participant): exactly their own parts, each with Confirm, and the
 * governed state of the measures they may see, where the person named for a field confirms Lens's guess. Nothing else of the baseline. */
function MyBaseline({ baselineId }: { baselineId: string }) {
  const [mine, setMine] = useState<MyParts | null>(null);
  const [gov, setGov] = useState<GovernedView | null>(null);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");
  const load = () => Promise.all([
    getMyParts(baselineId).then(setMine).catch(() => setMine({ status: "", parts: [] })),
    getGoverned(baselineId).then(setGov).catch(() => setGov(null)),
  ]);
  useEffect(() => void load(), [baselineId]);
  const run = (work: Promise<unknown>) => {
    setBusy(true);
    setNote("");
    work.then(() => { notifyChanged(); return load(); }).catch((e: unknown) => setNote(plain(e))).finally(() => setBusy(false));
  };
  const confirmField = (kpi: string) => (field: string, value: unknown) =>
    run(apiSend("POST", `/api/modules/m2_baseline/baselines/${encodeURIComponent(baselineId)}/governed/${encodeURIComponent(kpi)}/confirm`, { field, value }));
  if (!mine) return <EmptyState title="Opening your part of the baseline" lines={["Your measures are on their way."]} />;
  const open = mine.status === "open";
  return (
    <section aria-label={m2Signoff.mine.title} style={COLUMN}>
      <SideCard title={m2Signoff.mine.title}>
        <p>{mine.parts.length ? m2Signoff.mine.help : m2Signoff.mine.none}</p>
        <ul aria-label="Your parts">
        {mine.parts.map((p) => (
          <li key={`${p.kpi_id}-${p.part}`}>
            {m2Signoff.mine.line(p.kpi_name, p.label)}{" "}
            {p.confirmed ? <Pill tone="ok">{m2Signoff.mine.done}</Pill> : open ? (
              <Button variant="primary" disabled={busy} aria-label={`${m2Signoff.mine.confirm}: ${m2Signoff.mine.line(p.kpi_name, p.label)}`} onClick={() => run(confirmPart(baselineId, p.kpi_id, p.part))}>
                {m2Signoff.mine.confirm}
              </Button>
            ) : null}
          </li>
        ))}
        </ul>
        {note ? <p role="alert">{note}</p> : null}
      </SideCard>
      {(gov?.measures ?? []).filter((m) => mine.parts.some((p) => p.kpi_id === m.id)).map((m) => <GovernedState key={m.id} gov={gov} kpiId={m.id} onConfirm={open && !busy ? confirmField(m.id) : undefined} />)}
    </section>
  );
}

/** Glossary term and process map of the open measure, loaded when it opens. */
function Extras({ id, kpiId, signed }: { id: string; kpiId: string; signed: boolean }) {
  const [entry, setEntry] = useState<GlossaryEntry | null>(null);
  const [map, setMap] = useState<ProcessMap | null>(null);
  const [note, setNote] = useState("");
  useEffect(() => {
    getGlossary(id).then((g) => setEntry(g.entries.find((e) => e.kpi_id === kpiId) ?? null)).catch(() => setEntry(null));
    getProcessMap(id).then(setMap).catch(() => setMap(null));
  }, [id, kpiId]);
  const km = map?.kpis.find((x) => x.id === kpiId);
  const swap = (k: KpiMap) => map && setMap({ ...map, kpis: map.kpis.map((x) => (x.id === k.id ? k : x)) });
  return (
    <>
      <SideCard title="Glossary term">
        {entry ? (
          <>
            <Value label="Business definition in the glossary" p={entry.business_definition} />
            {entry.reviewed ? <Footnote>Reviewed by {entry.reviewed.by}</Footnote> : (
              <div>
                <Button disabled={signed}
                  onClick={() => reviewEntry(id, kpiId).then((g) => setEntry(g.entries.find((e) => e.kpi_id === kpiId) ?? null)).catch((e: unknown) => setNote(plain(e)))}>
                  Confirm term
                </Button>
              </div>
            )}
            {note ? <p role="alert">{note}</p> : null}
          </>
        ) : <Footnote>No glossary term yet.</Footnote>}
      </SideCard>
      {map && km ? <KpiMapPanel baselineId={id} kpi={km} statuses={map.statuses} signed={signed} onChange={swap} /> : null}
    </>
  );
}

/** One screen for the baseline: the measures, their status, filters, and the open measure's definitions, owners, access, glossary term and process map.
 * A link may open a measure straight away with ?measure=<id>; the sign-off panel sits beside the list (under it on a phone). */
export default function BaselinePage() {
  const { baselineId = "" } = useParams();
  const [params] = useSearchParams();
  const { user } = useSession();
  const me = user?.display_name ?? "";
  const loaded = useLoad(() => getWorkList(baselineId), `baseline-${baselineId}`);
  const govLoaded = useLoad(() => getGoverned(baselineId), `governed-${baselineId}`);
  const [fresh, setFresh] = useState<WorkList | null>(null);
  const [filter, setFilter] = useState<Filter>("all");
  const [selected, setSelected] = useState<string | null>(params.get("measure"));
  const [note, setNote] = useState("");
  const data = fresh ?? loaded.data;
  const locked = data?.baseline.state === "signed";

  const act = (p: Promise<WorkList>) =>
    p.then((v) => { setFresh(v); setNote(v.lens_note ?? ""); notifyChanged(); }).catch((e: unknown) => setNote(plain(e)));
  useEffect(() => {
    const again = () => getWorkList(baselineId).then(setFresh).catch(() => undefined);
    window.addEventListener(CHANGED, again);
    return () => window.removeEventListener(CHANGED, again);
  }, [baselineId]);

  const all = data?.kpis ?? [];
  const shown = all.filter((k: Kpi) =>
    filter === "all" || k.restricted ? true : filter === "mine" ? Object.values(k.owners).some((o) => o.value === me) : k.priority === filter);
  const chosen = all.find((k) => k.id === selected);
  const visible = all.filter((k): k is KpiFull => !k.restricted);
  const confirmed = visible.filter((k) => statusOf(k)[1] !== "draft").length;
  // The definition's button is the one-click Confirm the pulse sends the owner to; the other two name their field.
  const confirm = (field: Field, k: KpiFull) => (
    <div>
      <Button variant="primary" disabled={locked} aria-label={field === "definition" ? undefined : `Confirm: ${m2Work.fields[field]}`}
        onClick={() => act(putTriage(baselineId, k.id, { [field]: { text: k[field].value ?? "", mark: "stated" } }))}>
        Confirm
      </Button>
    </div>
  );

  let body: ReactNode;
  if (!data) {
    body = loaded.state === "loading" ? <EmptyState title="Opening the baseline" lines={["The measures and their definitions are on their way."]} />
      : loaded.state === "refused" ? <MyBaseline baselineId={baselineId} />
        : (
          <div role="alert">
            <EmptyState title="The baseline could not be loaded" lines={[loaded.message ?? "Please try again."]} />
            <Button onClick={loaded.retry}>Try again</Button>
          </div>
        );
  } else {
    body = (
      <>
        <div className="ds-frame__actions" role="group" aria-label="Filter">
          {FILTERS.map(([f, label]) => <Chip key={f} tone={filter === f ? "active" : "default"} onClick={() => setFilter(f)}>{label}</Chip>)}
        </div>
        {note ? <p role="status" className="ds-muted">{note}</p> : null}
        {shown.length === 0 ? <EmptyState title="No measures here yet" lines={["Try another filter."]} /> : (
          <DataTable
            columns={[{ key: "name", label: "Measure" }, { key: "priority", label: "Shelf" }, { key: "status", label: "Status" }]}
            rows={shown.map((k) => k.restricted
              ? { name: k.name, priority: "", status: <Pill tone="restricted">{m2Work.restricted}</Pill> }
              : {
                name: (
                  <button type="button" className="ds-link" style={LINK_BUTTON} aria-label={`Open: ${k.name}`} aria-current={k.id === selected ? "true" : undefined} onClick={() => setSelected(k.id)}>
                    {k.name}
                  </button>
                ),
                priority: k.priority ? k.priority.charAt(0).toUpperCase() + k.priority.slice(1) : "",
                status: <Pill tone={statusOf(k)[1]}>{statusOf(k)[0]}</Pill>,
              })}
          />
        )}

        {chosen && !chosen.restricted ? (
          <section aria-label={`Measure: ${chosen.name}`} style={COLUMN}>
            <SideCard title={chosen.name}>
              <Value label="Business definition" p={chosen.definition} confirm={confirm("definition", chosen)} />
              <Value label={m2Work.fields.producer} p={chosen.producer} confirm={confirm("producer", chosen)} />
              <Value label={m2Work.fields.gathered} p={chosen.gathered} confirm={confirm("gathered", chosen)} />
            </SideCard>
            <SideCard title="Owners, classification and who may see">
              {ROLES.map((r) => <Value key={r} label={OWNER[r]} p={chosen.owners[r]} />)}
              <div>
                <Footnote>Classification</Footnote>
                <p>{`${m2Work.personal} ${m2Work.personalOptions[chosen.governance.personal]}${chosen.governance.sensitive ? " · sensitive to the business" : ""}`}</p>
              </div>
              <div>
                <Footnote>Who may see</Footnote>
                <p>{chosen.governance.may_see.length ? chosen.governance.may_see.join(", ") : "Not confirmed yet"}</p>
              </div>
            </SideCard>
            <GovernedState gov={govLoaded.data ?? null} kpiId={chosen.id} />
            <Extras id={baselineId} kpiId={chosen.id} signed={locked} />
            <KpiDetail id={baselineId} kpi={chosen} me={me} locked={locked} act={act} onClose={() => setSelected(null)} />
          </section>
        ) : null}
      </>
    );
  }

  return (
    <PageFrame
      title="Baseline"
      subline={data ? `${confirmed} of ${visible.length} measures confirmed${locked ? " · signed and read-only" : ""}` : "The measures, their definitions and who signs them"}
      aside={data || loaded.state === "refused" ? <BaselineSignoff baselineId={baselineId} /> : undefined}
    >
      {body}
    </PageFrame>
  );
}
