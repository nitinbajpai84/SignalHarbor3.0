import { useEffect, useRef, useState } from "react";

import { ApiError, apiGet, apiSend, Refused } from "../../api/client";
import { Button, PageFrame, Pill } from "../../design";

// I1 Company page: who we are, systems, policies, documents. The decision maker edits in place and saves once.
// Upload and readBase64 copied from pages/ContextPage.tsx.

interface Cell { value: string | null; by: string | null; at: string | null }
interface System { id?: string; name: string | null; kind?: string | null; owner?: string | null; lands?: string | null; frequency?: string | null; restricted?: boolean }
interface Policy { kind: string; text: string; stated_by?: string; at?: string }
interface Doc { doc_id: string; title: string; filename: string; uploaded_at: string; restricted?: boolean }
export interface CompanyData {
  who: Record<string, Cell>;
  systems: System[];
  policies: Policy[];
  documents: Doc[];
  north_read_at: string | null;
  policy_kinds: string[];
  accepted: string[];
  max_mb: number;
  can_edit: boolean;
}

const API = "/api/v1/company";
const WHO: [string, string][] = [["name", "Name"], ["about", "What we do"], ["time_zone", "Time zone"], ["currency", "Reporting currency"]];
const SYS: [keyof System, string][] = [["name", "Name"], ["kind", "Kind"], ["owner", "Owner"], ["lands", "How it arrives"], ["frequency", "How often"]];
const when = (iso: string | null | undefined) => {
  const d = new Date(iso ?? "");
  return iso && !Number.isNaN(d.getTime()) ? d.toLocaleString() : "";
};
const say = (e: unknown) => (e instanceof ApiError && e.status !== 0 && e.status < 500 && e.message ? e.message : "That did not work. Please try again.");

function readBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve(String(r.result).split(",", 2)[1] ?? "");
    r.onerror = () => reject(new Error("unreadable"));
    r.readAsDataURL(file);
  });
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="ds-card" style={{ marginBottom: 16 }}>
      <h2 style={{ fontSize: 18, margin: "0 0 12px" }}>{title}</h2>
      {children}
    </section>
  );
}

const field = { display: "flex", flexDirection: "column", gap: 4, flex: "1 1 160px", minWidth: 0 } as const;
const label = { fontSize: 12 } as const;

export default function CompanyPage() {
  const [data, setData] = useState<CompanyData | null>(null);
  const [state, setState] = useState<"loading" | "error" | "refused" | "ready">("loading");
  const [who, setWho] = useState<Record<string, string>>({});
  const [systems, setSystems] = useState<System[]>([]);
  const [policies, setPolicies] = useState<Policy[]>([]);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const take = (d: CompanyData) => {
    setData(d);
    setWho(Object.fromEntries(WHO.map(([k]) => [k, d.who[k]?.value ?? ""])));
    setSystems(d.systems);
    setPolicies(d.policies);
    setState("ready");
  };
  const load = () => {
    setState("loading");
    apiGet<CompanyData>(API).then(take).catch((e: unknown) => setState(e instanceof Refused ? "refused" : "error"));
  };
  useEffect(load, []);

  const save = async () => {
    setBusy(true);
    try {
      const sys = systems.filter((s) => !s.restricted && (s.id || s.name?.trim()))
        .map((s) => Object.fromEntries([...(s.id ? [["id", s.id]] : []), ...SYS.map(([k]) => [k, (s[k] as string | null) ?? ""])]));
      take(await apiSend<CompanyData>("PUT", API, { who, systems: sys, policies: policies.filter((p) => p.text.trim()) }));
      setNote("Saved.");
    } catch (e) {
      setNote(say(e));
    } finally {
      setBusy(false);
    }
  };

  const upload = async () => {
    const file = fileRef.current?.files?.[0];
    if (!file) return setNote("Choose a file first.");
    if (data && file.size > data.max_mb * 1024 * 1024) return setNote(`That file is too large. The limit is ${data.max_mb} MB.`);
    setBusy(true);
    try {
      await apiSend("POST", `${API}/documents`, { filename: file.name, data: await readBase64(file) });
      if (fileRef.current) fileRef.current.value = "";
      setNote(`${file.name} added.`);
      take(await apiGet<CompanyData>(API));
    } catch (e) {
      setNote(e instanceof Error && e.message === "unreadable" ? "That file could not be read." : say(e));
    } finally {
      setBusy(false);
    }
  };

  if (state === "loading") return <div className="ds-screen"><p role="status" className="ds-muted">Loading…</p></div>;
  if (state !== "ready" || !data)
    return (
      <div className="ds-screen">
        <p role="alert" className="ds-warn">{state === "refused" ? "The company page is not open to your role." : "The company page could not be loaded."}</p>
        {state === "error" && <Button onClick={load}>Try again</Button>}
      </div>
    );

  const edit = data.can_edit;
  const setSys = (i: number, k: keyof System, v: string) => setSystems((all) => all.map((s, j) => (j === i ? { ...s, [k]: v } : s)));
  const setPol = (i: number, p: Partial<Policy>) => setPolicies((all) => all.map((x, j) => (j === i ? { ...x, ...p } : x)));

  return (
    <div className="ds-screen">
      <PageFrame title="Company page" subline="What North reads before it asks you anything.">
        <p className="ds-muted" role="note">
          {data.north_read_at ? `North has read this: ${when(data.north_read_at)}.` : "North has not read this yet."}
        </p>

        <Section title="Who we are">
          <div style={{ display: "flex", flexWrap: "wrap", gap: 12 }}>
            {WHO.map(([k, l]) => (
              <label key={k} style={field}>
                <span className="ds-muted" style={label}>{l}</span>
                {edit ? <input className="ds-input" aria-label={l} value={who[k] ?? ""} onChange={(e) => setWho({ ...who, [k]: e.target.value })} />
                  : <span>{who[k] || "Not said yet"}</span>}
              </label>
            ))}
          </div>
        </Section>

        <Section title="Systems">
          {systems.length === 0 && <p className="ds-muted">No systems yet.</p>}
          {systems.map((s, i) => s.restricted ? (
            <p key={s.id} className="ds-muted"><Pill tone="restricted">Restricted</Pill> {s.name}</p>
          ) : (
            <div key={s.id ?? `new-${i}`} style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 12 }}>
              {SYS.map(([k, l]) => (
                <label key={k} style={field}>
                  <span className="ds-muted" style={label}>{l}</span>
                  {edit ? <input className="ds-input" aria-label={`${l} of system ${i + 1}`} value={(s[k] as string | null) ?? ""} onChange={(e) => setSys(i, k, e.target.value)} />
                    : <span>{(s[k] as string | null) || "Not said yet"}</span>}
                </label>
              ))}
            </div>
          ))}
          {edit && <Button onClick={() => setSystems([...systems, { name: "" }])}>Add a system</Button>}
        </Section>

        <Section title="Policies">
          {policies.length === 0 && <p className="ds-muted">No policies yet.</p>}
          {policies.map((p, i) => (
            <div key={i} style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 12, alignItems: "flex-end" }}>
              {edit ? (
                <>
                  <select className="ds-input" aria-label={`Kind of policy ${i + 1}`} value={p.kind} onChange={(e) => setPol(i, { kind: e.target.value })}>
                    {data.policy_kinds.map((k) => <option key={k} value={k}>{k}</option>)}
                  </select>
                  <input className="ds-input" style={{ flex: "1 1 240px" }} aria-label={`Policy ${i + 1}`} value={p.text} onChange={(e) => setPol(i, { text: e.target.value })} />
                  <Button onClick={() => setPolicies(policies.filter((_, j) => j !== i))}>Remove</Button>
                </>
              ) : (
                <span><Pill tone="draft">{p.kind}</Pill> {p.text}</span>
              )}
              {p.stated_by && <span className="ds-muted" style={label}>Stated by {p.stated_by}, {when(p.at)}</span>}
            </div>
          ))}
          {edit && <Button onClick={() => setPolicies([...policies, { kind: data.policy_kinds[0] ?? "other", text: "" }])}>Add a policy</Button>}
        </Section>

        {edit && (
          <div style={{ margin: "0 0 16px" }}>
            <Button variant="primary" disabled={busy} onClick={save}>{busy ? "Saving…" : "Save"}</Button>
          </div>
        )}

        <Section title="Documents">
          {data.documents.length === 0 && <p className="ds-muted">No documents yet.</p>}
          <ul style={{ paddingLeft: 18 }}>
            {data.documents.map((d) => (
              <li key={d.doc_id}>{d.title} <span className="ds-muted" style={label}>added {when(d.uploaded_at)}{d.restricted ? ", restricted" : ""}</span></li>
            ))}
          </ul>
          {edit && (
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center" }}>
              <input className="ds-input" type="file" aria-label="Document to add" ref={fileRef} />
              <Button disabled={busy} onClick={upload}>Add document</Button>
              <span className="ds-muted" style={label}>{data.accepted.join(", ")}; up to {data.max_mb} MB.</span>
            </div>
          )}
        </Section>

        {note && <p role="status" className="ds-muted">{note}</p>}
      </PageFrame>
    </div>
  );
}
