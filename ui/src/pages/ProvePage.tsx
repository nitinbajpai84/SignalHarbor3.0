import HandOverStrip from "./build/HandOverStrip";
import { useCallback, useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";

import { apiGet, apiSend, Refused } from "../api/client";
import { Button, DataTable, EmptyState, Footnote, PageFrame, Pill, SideCard, Signature, type PillTone } from "../design";
import { useSession } from "../useSession";

// Prove and release. Shape: docs/plan/SHAPES.md section 5, plus name, tester, rules and sponsor as served by sh_platform/build/prove.py.
interface Period { period: string; ours: number | null; reported: number | null; result: "match" | "gap" | "not_yet"; reason: string | null; accepted_by: string | null }
interface Uat { state: "pending" | "signed" | "sent_back"; by?: string | null; at?: string | null; note?: string | null }
interface Measure { code: string; name?: string; tester?: string | null; periods: Period[]; uat: Uat; release_ready: boolean; changed?: string[]; waits_for?: string | null; rules?: { failed: number; passed: number } | null }
interface Check { version: number; at: string; by: string; reason: string; changed: string[]; voided: string[] }
interface Prove { checks?: Check[]; band?: string; sponsor?: string | null; measures: Measure[]; release: { state: "draft" | "signed"; by?: string | null; at?: string | null; sponsor?: string | null; released?: string[]; held_back?: { code: string; reason: string }[] } }
type Load = "loading" | "error" | "refused" | "ready";

const NA = "Not available yet";
const TONE: Record<Period["result"], PillTone> = { match: "ok", gap: "late", not_yet: "draft" };
const LABEL: Record<Period["result"], string> = { match: "Match", gap: "Gap", not_yet: "Not yet" };
const num = (v: number | null | undefined) => (v === null || v === undefined ? NA : v.toLocaleString("en-GB", { maximumFractionDigits: 2 }));
const day = (t?: string | null) => { const d = t ? new Date(t) : null; return d && !isNaN(+d) ? d.toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" }) : undefined; };
const diff = (p: Period) => (p.ours === null || p.reported === null ? NA : String(Number((p.ours - p.reported).toFixed(2))));
const same = (a: string | null | undefined, b: string | null | undefined) => !!a && !!b && a.trim().toLowerCase() === b.trim().toLowerCase();

export default function ProvePage() {
  const { user } = useSession();
  const [data, setData] = useState<Prove | null>(null);
  const [load, setLoad] = useState<Load>("loading");
  const [open, setOpen] = useState<string | null>(null);
  const [note, setNote] = useState<Record<string, string>>({});
  const [msg, setMsg] = useState<string | null>(null);

  const read = useCallback(() => {
    apiGet<Prove>("/api/company/build/prove")
      .then((d) => { setData(d); setLoad("ready"); })
      .catch((e: unknown) => setLoad(e instanceof Refused ? "refused" : "error"));
  }, []);
  useEffect(read, [read]);

  const send = (path: string, body: unknown) =>
    apiSend("POST", path, body).then(() => { setMsg(null); read(); })
      .catch((e: unknown) => setMsg(e instanceof Error && e.message ? e.message : "That did not go through. Try again."));

  const me = user?.display_name ?? null;
  const roles = user?.roles ?? [];
  const canAccept = roles.some((r) => r === "company_admin" || r === "owner");
  // The route lets only the named tester sign; with no tester named, the sponsor or a company admin (sh_platform/build/uat.py).
  const canSign = (m: Measure) => (m.tester ? same(m.tester, me) : roles.some((r) => r === "sponsor" || r === "company_admin"));
  const canRecheck = (m: Measure) => roles.some((r) => r === "company_admin" || r === "sponsor" || r === "analyst") || same(m.tester, me);
  const measures = data?.measures ?? [];
  const held = measures.filter((m) => !m.release_ready);
  const ready = measures.length - held.length;
  const waits = held.map((m) => `${m.code} ${m.waits_for ? `waits for ${m.waits_for}` : "is not ready"}`).join("; ");
  const rel = data?.release;
  const sponsor = data?.sponsor ?? rel?.sponsor ?? null;
  const isSponsor = sponsor ? same(sponsor, me) : roles.includes("sponsor");

  const frame = (body: ReactNode, aside?: ReactNode) => (
    <div className="ds-screen">
      <PageFrame title="Prove and release" crumbs="Build · Room 2: Build the data"
        subline={data && measures.length ? `${ready} of ${measures.length} measures ready to release${data.band ? (data.band === "now" ? " · Planned for now" : ` · Band ${data.band}`) : ""}` : "Each measure is recomputed from the warehouse and compared with the reported figure."}
        aside={aside}>
        <HandOverStrip />
        {body}
      </PageFrame>
    </div>
  );

  if (load === "loading") return frame(<EmptyState title="Reading the Prover's results" lines={["Each measure and its periods are on their way."]} />);
  if (load === "error") return frame(<><EmptyState title="The results could not be read" lines={["Nothing was changed. Try again in a moment."]} /><Button onClick={read}>Try again</Button></>);
  if (load === "refused") return frame(<EmptyState title="Prove and release is not open to you" lines={["Ask your company admin to share it if you test or release a measure."]} />);
  if (!measures.length) return frame(<EmptyState title="Nothing to prove yet" lines={["The Prover checks each measure once its pipelines have run."]} links={[{ label: "Open the pipelines", href: "/centre/build/pipelines" }]} />);

  return frame(
    <>
      {msg && <p role="alert" className="ds-warn">{msg}</p>}
      {waits && <p>{waits}.</p>}
      {measures.map((m) => (
        <SideCard key={m.code} title={m.name ?? m.code}>
          <p><Pill tone={m.release_ready ? "ok" : "late"}>{m.release_ready ? "Ready to release" : "Not ready"}</Pill></p>
          <DataTable
            columns={[{ key: "period", label: "Period" }, { key: "ours", label: "Ours" }, { key: "reported", label: "Reported" }, { key: "diff", label: "Difference" },
              { key: "result", label: "Result" }, { key: "reason", label: "Reason" }]}
            rows={m.periods.map((p) => {
              const k = m.code + p.period;
              return {
                period: p.period, ours: num(p.ours), reported: num(p.reported), diff: diff(p),
                result: <Pill tone={TONE[p.result]}>{LABEL[p.result]}</Pill>,
                reason: (
                  <>
                    {p.reason && <span className="ds-warn">{p.reason}</span>}
                    {p.accepted_by && <span className="ds-muted"> Accepted by {p.accepted_by}</span>}
                    {p.result === "gap" && !p.accepted_by && canAccept && (
                      <div className="ds-comment__decide">
                        <input aria-label={`Reason to accept ${m.code} ${p.period}`} placeholder="Why the gap is acceptable" value={note[k] ?? ""}
                          onChange={(e) => setNote({ ...note, [k]: e.target.value })} />
                        <Button disabled={!(note[k] ?? "").trim()} onClick={() => void send(`/api/company/build/prove/${encodeURIComponent(m.code)}/accept`, { period: p.period, reason: note[k] })}>Accept the gap</Button>
                      </div>
                    )}
                  </>
                ),
              };
            })}
          />
          {m.changed?.length ? (
            <div className="ds-comment__decide">
              <p className="ds-warn">{`The result changed for ${m.changed.join(", ")} after the tester signed.`}</p>
              {canRecheck(m) && (
                <>
                  <input aria-label={`Reason to re-check ${m.code}`} placeholder="Why you are re-checking" value={note["re" + m.code] ?? ""} onChange={(e) => setNote({ ...note, ["re" + m.code]: e.target.value })} />
                  <Button disabled={!(note["re" + m.code] ?? "").trim()} onClick={() => void send("/api/company/build/prove/recheck", { reason: note["re" + m.code] })}>Re-check figures</Button>
                </>
              )}
            </div>
          ) : null}
          <Signature state={m.uat.state === "signed" ? "signed" : "waiting"} by={(m.uat.state === "signed" ? m.uat.by : m.tester) ?? undefined} at={m.uat.state === "signed" ? day(m.uat.at) : undefined} />
          {m.uat.state === "sent_back" && <p className="ds-warn">Sent back{m.uat.by ? ` by ${m.uat.by}` : ""}{m.uat.note ? `: ${m.uat.note}` : ""}</p>}
          {m.uat.state !== "signed" && canSign(m) && (
            <div className="ds-comment__decide">
              <input aria-label={`UAT note for ${m.code}`} placeholder="A note for the data team" value={note[m.code] ?? ""} onChange={(e) => setNote({ ...note, [m.code]: e.target.value })} />
              <Button variant="primary" onClick={() => void send(`/api/company/build/uat/${encodeURIComponent(m.code)}/sign`, { state: "signed", note: note[m.code] ?? "" })}>Sign UAT</Button>
              <Button disabled={!(note[m.code] ?? "").trim()} onClick={() => void send(`/api/company/build/uat/${encodeURIComponent(m.code)}/sign`, { state: "sent_back", note: note[m.code] })}>Send back with a note</Button>
            </div>
          )}
          <p>{m.tester ? `Tester: ${m.tester}` : "No tester is named on the charter, so the sponsor or a company admin signs."}</p>
          <div className="ds-frame__actions">
            <Button aria-expanded={open === m.code} onClick={() => setOpen(open === m.code ? null : m.code)}>Evidence</Button>
          </div>
          {open === m.code && (
            <>
              <p>Periods checked: {m.periods.map((p) => p.period).join(", ") || "none"}</p>
              <p className={m.rules?.failed ? "ds-warn" : undefined}>{m.rules ? `Rules in the latest run: ${m.rules.passed} passed, ${m.rules.failed} failed` : `Rules: ${NA}`}</p>
              <p><Link to={`/centre/intent/map/${encodeURIComponent(m.code)}`}>See where it comes from</Link></p>
            </>
          )}
        </SideCard>
      ))}
    </>,
    <>
      <SideCard title="Release">
        {rel?.state === "signed" ? <p><Pill tone="signed">Signed</Pill> {`Released by ${rel.by ?? "the sponsor"}${day(rel.at) ? ` on ${day(rel.at)}` : ""}${rel.held_back?.length ? ` · ${rel.held_back.length} held back` : ""}`}</p> : (
          <>
            {!held.length && <p>Every measure is ready.</p>}
            <Signature state="waiting" by={sponsor ?? undefined} />
            {isSponsor
              ? <Button variant="primary" disabled={ready === 0} onClick={() => void send("/api/company/build/release/sign", {})}>{`Release ${ready} measure${ready === 1 ? "" : "s"}`}</Button>
              : <p>{sponsor ? `Only ${sponsor}, the sponsor, signs the release.` : "The sponsor signs the release."}</p>}
          </>
        )}
      </SideCard>
      {!!data?.checks?.length && (
        <SideCard title="Re-checks">
          {[...data.checks].reverse().map((c) => (
            <p key={c.version}>{`${c.by}, ${day(c.at) ?? ""}: ${c.reason}. ${c.changed.length ? `Changed: ${c.changed.join(", ")}` : "Nothing changed"}${c.voided.length ? `; signature voided: ${c.voided.join(", ")}` : ""}.`}</p>
          ))}
        </SideCard>
      )}
      <Footnote>Ours is recomputed from the warehouse; reported is the company's own figure. A gap counts as ready only with an accepted reason.</Footnote>
    </>,
  );
}
