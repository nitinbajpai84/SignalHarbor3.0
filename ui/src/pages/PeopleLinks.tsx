import { useCallback, useEffect, useState } from "react";

import { ApiError, apiGet, apiSend, Refused } from "../api/client";
import Panel from "../components/Panel";
import ScreenState, { type ScreenStateName } from "../components/ScreenState";
import StatusPill from "../components/StatusPill";

// People section of "Bring what you have": the company admin links each person on the profile to one sign-in account of the company.
// Shown to the company admin only (the server refuses everyone else, and then this section is simply not there).
const c = {
  title: "People and their accounts",
  sub: "Link each person to the account they sign in with, so their interview and answers reach the right person. The match is made on what you choose here, never on a name.",
  empty: "No people have been read yet. Bring the people list above first.",
  failed: "That did not work. Try again.",
  none: "Not linked",
  pick: (n: string) => `Linked account for ${n}`,
  suggested: (account: string, file: string | null) => `Suggestion: ${account}, matched by email${file ? ` in ${file}` : ""}. Nothing is linked until you confirm it or pick another account.`,
  unlinkNote: "If you choose Not linked, that person will not be suggested again.",
  confirm: "Confirm",
  saved: (n: string) => `Saved for ${n}.`,
  loading: "Loading people...",
};

interface Person { id: string; name: string; role: string | null; team: string | null; account_id: string | null; link_from: string | null; suggestion: { account_id: string; file: string | null } | null }
interface Account { account_id: string; display_name: string }
interface Links { people: Person[]; accounts: Account[] }

const say = (e: unknown) => (e instanceof ApiError && e.status !== 0 && e.status < 500 && e.message ? e.message : c.failed);

export default function PeopleLinks() {
  const [state, setState] = useState<ScreenStateName>("loading");
  const [data, setData] = useState<Links | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [note, setNote] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    let live = true;
    setState("loading");
    apiGet<Links>("/api/profile/links")
      .then((r) => {
        if (!live) return;
        setData(r);
        setState(r.people.length === 0 ? "empty" : "populated");
      })
      .catch((e: unknown) => live && setState(e instanceof Refused ? "refused" : "error"));
    return () => {
      live = false;
    };
  }, [attempt]);
  const reload = useCallback(() => setAttempt((a) => a + 1), []);

  const save = async (p: Person, account: string | null) => {
    setNote("");
    setError("");
    try {
      await apiSend("PUT", `/api/profile/people/${encodeURIComponent(p.id)}/account`, { account_id: account });
      setNote(c.saved(p.name));
      reload();
    } catch (e) {
      setError(say(e));
    }
  };

  if (state === "refused") return null;
  return (
    <Panel title={c.title}>
      <p className="n-muted" style={{ fontSize: 12 }}>{c.sub}</p>
      {state !== "populated" ? <ScreenState state={state} onRetry={reload} message={state === "empty" ? c.empty : state === "loading" ? c.loading : undefined} /> : null}
      <p className="n-muted" style={{ fontSize: 12 }}>{c.unlinkNote}</p>
      {error ? <p role="alert" className="state state-error">{error}</p> : null}
      {note ? <p role="status" className="n-muted">{note}</p> : null}
      {data && state === "populated" ? (
        <div className="n-stack">
          {data.people.map((p) => {
            const taken = new Set(data.people.filter((o) => o.id !== p.id && o.account_id).map((o) => o.account_id));
            return (
              <div key={p.id} className="n-ambig-row n-flex between" aria-label={p.name} role="group">
                <div>
                  <div className="n-ambig-title">{p.name}</div>
                  <div className="n-ambig-detail">{[p.role, p.team].filter(Boolean).join(", ")}</div>
                  {p.suggestion ? <p className="n-muted" style={{ fontSize: 12 }}><StatusPill tone="info">Suggestion</StatusPill> {c.suggested(data.accounts.find((a) => a.account_id === p.suggestion?.account_id)?.display_name ?? "an account", p.suggestion.file)}</p> : null}
                </div>
                <div className="n-flex" style={{ gap: 6 }}>
                  <select className="n-input sm" aria-label={c.pick(p.name)} value={p.account_id ?? ""} onChange={(e) => save(p, e.target.value || null)}>
                    <option value="">{c.none}</option>
                    {data.accounts.map((a) => <option key={a.account_id} value={a.account_id} disabled={taken.has(a.account_id)}>{a.display_name}</option>)}
                  </select>
                  {p.suggestion ? <button type="button" className="n-btn sm" onClick={() => save(p, p.suggestion!.account_id)}>{c.confirm}</button> : null}
                </div>
              </div>
            );
          })}
        </div>
      ) : null}
    </Panel>
  );
}
