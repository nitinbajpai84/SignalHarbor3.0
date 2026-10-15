import { useCallback, useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";

import { apiGet, apiSend } from "../api/client";
import Panel from "../components/Panel";
import ScreenState from "../components/ScreenState";
import { Button, Chip, PageFrame } from "../design";

/** Company areas (/centre/intent/admin/areas) and People and areas (/centre/intent/admin/areas/people), company admin only (spec 05, screens A and B).
 *  One component for both routes: it reads the path, so App.tsx can mount it on each. */

interface Area { id: string; name: string; kind: string; status: string }
interface Suggested { id: string; name: string; kind: string; note: string }
interface Lens { teams: string[]; tags: { pid: string; name: string; area_id: string; area_name: string }[] }
interface Cell { value?: unknown }
type Person = Record<string, Cell>;

const KIND: Record<string, string> = { department: "Department", operations_area: "Operations area" };
const grid = { display: "grid", gap: 16, gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 320px), 1fr))", alignItems: "start" } as const;
const row = { display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center", padding: "10px 0", borderBottom: "1px solid var(--ds-line)" } as const;
const text = (p: Person, k: string) => (typeof p[k]?.value === "string" ? (p[k].value as string) : "");
const tags = (p: Person) => (Array.isArray(p.areas?.value) ? (p.areas.value as string[]) : []);

function useAreasData() {
  const [state, setState] = useState<"loading" | "error" | "refused" | "populated">("loading");
  const [areas, setAreas] = useState<Area[]>([]);
  const [peopleFile, setPeopleFile] = useState(false);
  const [titlesPrivate, setTitlesPrivate] = useState(false);
  const [sugg, setSugg] = useState<{ suggested: Suggested[]; lens: Lens; all_taken?: boolean }>({ suggested: [], lens: { teams: [], tags: [] } });
  const [people, setPeople] = useState<Record<string, Person>>({});
  const load = useCallback(async () => {
    try {
      const [a, s, p] = await Promise.all([
        apiGet<{ areas: Area[]; people_file: boolean; titles_private?: boolean }>("/api/company/areas"),
        apiGet<{ suggested: Suggested[]; lens: Lens; all_taken?: boolean }>("/api/profile/areas/suggestions"),
        apiGet<{ people: Record<string, Person> }>("/api/profile"),
      ]);
      setAreas(a.areas); setPeopleFile(a.people_file); setTitlesPrivate(a.titles_private === true); setSugg(s); setPeople(p.people);
      setState("populated");
    } catch (e) {
      setState((e as { status?: number }).status === 403 ? "refused" : "error");
    }
  }, []);
  useEffect(() => { void load(); }, [load]);
  return { state, areas, peopleFile, titlesPrivate, sugg, people, load };
}

export default function AreasAdmin() {
  const onPeople = useLocation().pathname.replace(/\/$/, "").endsWith("/people");
  const data = useAreasData();
  return (
    <PageFrame
      title={onPeople ? "People and areas" : "Company areas"}
      subline={onPeople ? "Tag each person to the areas they work in. A tag lets them see that an intent exists." : "Areas are the departments and operations areas your intents are about."}
      actions={<Chip href={onPeople ? "/centre/intent/admin/areas" : "/centre/intent/admin/areas/people"}>{onPeople ? "Company areas" : "People and areas"}</Chip>}
    >
      <ScreenState state={data.state} message={data.state === "refused" ? "Only the company admin can set up areas." : undefined} onRetry={() => void data.load()}>
        {onPeople ? <PeopleAndAreas {...data} /> : <CompanyAreas {...data} />}
      </ScreenState>
    </PageFrame>
  );
}

type Data = ReturnType<typeof useAreasData>;

function CompanyAreas({ areas, peopleFile, titlesPrivate, sugg, people, load }: Data) {
  const [name, setName] = useState("");
  const [kind, setKind] = useState("department");
  const [error, setError] = useState("");
  const [showRetired, setShowRetired] = useState(false);
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [retiring, setRetiring] = useState<string | null>(null);
  const [ticked, setTicked] = useState<string[]>([]);
  const [hideLens, setHideLens] = useState(false);
  const [intents, setIntents] = useState<Record<string, number | null>>({});

  useEffect(() => {
    let live = true;
    // The list route answers an array of what this viewer may see (or {total} in the spec's shape); either way the count is this viewer's own.
    void Promise.all(areas.map((a) => apiGet<unknown[] | { total: number }>(`/api/intents?area=${encodeURIComponent(a.id)}`)
      .then((r) => [a.id, Array.isArray(r) ? r.length : typeof r.total === "number" ? r.total : null] as const).catch(() => [a.id, null] as const)))
      .then((r) => { if (live) setIntents(Object.fromEntries(r)); });
    return () => { live = false; };
  }, [areas]);

  const act = async (fn: () => Promise<unknown>) => {
    setError("");
    try { await fn(); await load(); return true; } catch (e) { setError((e as Error).message); return false; }
  };
  const count = (id: string) => (peopleFile ? Object.values(people).filter((p) => tags(p).includes(id)).length : null);
  const visible = areas.filter((a) => showRetired || a.status !== "retired");

  return (
    <div style={grid}>
      <Panel title="Your areas" actions={<Chip tone={showRetired ? "active" : "default"} onClick={() => setShowRetired(!showRetired)}>Show retired</Chip>}>
        <form style={{ ...row, borderBottom: 0 }} onSubmit={(e) => { e.preventDefault(); void act(() => apiSend("POST", "/api/profile/areas", { name, kind })).then((ok) => ok && setName("")); }}>
          <input type="text" aria-label="Area name" placeholder="Area name" value={name} onChange={(e) => setName(e.target.value)} maxLength={60} />
          <select aria-label="Kind" value={kind} onChange={(e) => setKind(e.target.value)}>
            <option value="department">Department</option>
            <option value="operations_area">Operations area</option>
          </select>
          <Button type="submit" variant="primary" disabled={!name.trim()}>Add area</Button>
        </form>
        {error ? <p role="alert" className="ds-warn">{error}</p> : null}
        {visible.length === 0 ? <p className="n-muted">No areas yet. Add one, or accept the suggestions.</p> : visible.map((a) => (
          <div key={a.id} style={row} data-testid="area-row">
            <strong style={{ flex: "1 1 160px" }}>{a.name}{a.status === "retired" ? " (retired)" : ""}</strong>
            <span className="n-muted">{KIND[a.kind] ?? a.kind}</span>
            <span className="n-muted">
              {peopleFile ? `${count(a.id)} tagged` : "People: Not available yet: no people file read"}
              {" · "}{intents[a.id] == null ? "Intents: Not available yet" : `${intents[a.id]} intents`}
            </span>
            {editing === a.id ? (
              <>
                <input type="text" aria-label={`New name for ${a.name}`} value={draft} onChange={(e) => setDraft(e.target.value)} maxLength={60} />
                <Button variant="primary" disabled={!draft.trim()} onClick={() => void act(() => apiSend("PUT", `/api/profile/areas/${a.id}`, { name: draft })).then((ok) => ok && setEditing(null))}>Save</Button>
                <Button onClick={() => setEditing(null)}>Cancel</Button>
              </>
            ) : retiring === a.id ? (
              <>
                <span>People and past intents keep this area. It will not be offered for new intents.</span>
                <Button variant="primary" onClick={() => void act(() => apiSend("POST", `/api/profile/areas/${a.id}/retire`)).then(() => setRetiring(null))}>Retire</Button>
                <Button onClick={() => setRetiring(null)}>Cancel</Button>
              </>
            ) : a.status === "retired" ? (
              <Button onClick={() => void act(() => apiSend("POST", `/api/profile/areas/${a.id}/restore`))}>Bring back</Button>
            ) : (
              <>
                <Button onClick={() => { setEditing(a.id); setDraft(a.name); }}>Rename</Button>
                <Button onClick={() => setRetiring(a.id)}>Retire</Button>
              </>
            )}
          </div>
        ))}
        {sugg.lens.teams.length > 0 && !hideLens ? (
          <div style={row}>
            <span>Lens: Your people file lists teams not yet areas: {sugg.lens.teams.join(", ")}. Add them?</span>
            <Button variant="primary" onClick={() => void act(() => apiSend("POST", "/api/profile/areas/teams", { teams: sugg.lens.teams }))}>Add</Button>
            <Button onClick={() => setHideLens(true)}>Not now</Button>
          </div>
        ) : null}
        <label style={{ ...row, borderBottom: 0 }}>
          <input type="checkbox" checked={titlesPrivate} onChange={(e) => void act(() => apiSend("PUT", "/api/profile/areas/settings", { titles_private: e.target.checked }))} />
          Keep intent titles private to the company
        </label>
      </Panel>

      <Panel title="Suggested for a family office" eyebrow="Suggestion">
        <p className="n-muted">What others in a family office usually have. These are suggestions, not your company's own areas.</p>
        {sugg.suggested.length === 0 ? <p className="n-muted">{sugg.all_taken ? "Every suggestion is already one of your areas." : "No suggestions for this industry yet. Add your own."}</p> : sugg.suggested.map((s) => (
          <label key={s.id} style={{ ...row, display: "flex" }}>
            <input type="checkbox" checked={ticked.includes(s.id)} onChange={() => setTicked(ticked.includes(s.id) ? ticked.filter((i) => i !== s.id) : [...ticked, s.id])} />
            <span><strong>{s.name}</strong> <span className="n-muted">{KIND[s.kind] ?? s.kind}. {s.note}</span></span>
          </label>
        ))}
        <Button variant="primary" disabled={ticked.length === 0} onClick={() => void act(() => apiSend("POST", "/api/profile/areas/accept", { ids: ticked })).then((ok) => ok && setTicked([]))}>Add selected</Button>
      </Panel>
    </div>
  );
}

function PeopleAndAreas({ areas, people, sugg, load }: Data) {
  const [onlyUntagged, setOnlyUntagged] = useState(false);
  const [toast, setToast] = useState("");
  const [error, setError] = useState("");
  const active = areas.filter((a) => a.status === "active");
  const all = Object.entries(people);
  const untagged = all.filter(([, p]) => tags(p).length === 0);
  const shown = onlyUntagged ? untagged : all;

  const [busy, setBusy] = useState(false);
  const save = async (pid: string, next: string[], said: string) => {
    if (busy) return; // a second click before the reload would send a stale list and drop the first tag
    setBusy(true);
    setError("");
    try {
      await apiSend("PUT", `/api/profile/people/${pid}/areas`, { areas: next });
      setToast(said);
      await load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const toggle = (pid: string, p: Person, a: Area) => {
    const mine = tags(p);
    const first = (text(p, "name") || pid).split(" ")[0];
    const on = mine.includes(a.id);
    void save(pid, on ? mine.filter((i) => i !== a.id) : [...mine, a.id], `${first} ${on ? "no longer sees" : "now sees"} intents in ${a.name}`);
  };

  if (all.length === 0) {
    return <ScreenState state="empty" message="No people in the profile yet. Bring what you have first."><span /></ScreenState>;
  }
  return (
    <Panel title="People" actions={<Chip tone={onlyUntagged ? "active" : "default"} onClick={() => setOnlyUntagged(!onlyUntagged)}>{untagged.length === 0 ? "Everyone is tagged" : `${untagged.length} with no area`}</Chip>}>
      <p className="n-muted"><Link to="/company/context">Bring what you have</Link> to add people to the profile.</p>
      {toast ? <p role="status">{toast}</p> : null}
      {error ? <p role="alert" className="ds-warn">{error}</p> : null}
      {sugg.lens.tags.length > 0 ? sugg.lens.tags.map((t) => (
        <div key={t.pid} style={row}>
          <span>Lens: Team says {t.area_name} for {t.name}. Tag {t.name} to {t.area_name}?</span>
          <Button variant="primary" onClick={() => void save(t.pid, [t.area_id], `${t.name.split(" ")[0]} now sees intents in ${t.area_name}`)}>Accept</Button>
        </div>
      )) : null}
      {shown.map(([pid, p]) => {
        const mine = tags(p);
        const linked = typeof p.account_id?.value === "string" && p.account_id.value !== "";
        return (
          <div key={pid} style={row} data-testid="person-row">
            <strong style={{ flex: "1 1 160px" }}>{text(p, "name") || pid}</strong>
            <span className="n-muted">{text(p, "role") || "Role not given"}{text(p, "team") ? ` · ${text(p, "team")}` : ""}</span>
            {mine.length === 0 ? <span className="ds-warn">No area</span> : null}
            <span style={{ display: "flex", flexWrap: "wrap", gap: 6 }} role="group" aria-label={`Areas for ${text(p, "name") || pid}`}>
              {active.map((a) => <Chip key={a.id} tone={mine.includes(a.id) ? "active" : "default"} onClick={() => toggle(pid, p, a)}>{a.name}</Chip>)}
            </span>
            {linked ? null : <Link to="/company/context" className="n-muted">No sign-in account linked: this person sees nothing yet</Link>}
          </div>
        );
      })}
    </Panel>
  );
}
