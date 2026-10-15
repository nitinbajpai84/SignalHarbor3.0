import { useEffect, useState } from "react";

import { ApiError, apiGet, apiSend } from "../../api/client";

// People and access, administrator only: give a colleague a different role (for example the risk owner who must decide breaches).
interface Person { account_id: string; name: string; roles: string[] }
interface Roles { choices: string[]; people: Person[] }

const LABEL: Record<string, string> = {
  participant: "Participant (reads, asks and notes)", owner: "Owner (takes and decides cases)", approver: "Approver",
  analyst: "Analyst (data team)", sponsor: "Sponsor", company_admin: "Company administrator",
};

export default function PeopleRoles() {
  const [data, setData] = useState<Roles | null>(null);
  const [msg, setMsg] = useState("");
  const load = () => apiGet<Roles>("/api/v1/people/roles").then(setData).catch(() => setData(null));
  useEffect(() => { void load(); }, []);
  if (!data) return null; // only the administrator gets the list
  const change = async (p: Person, role: string) => {
    try {
      await apiSend("PUT", `/api/v1/people/${encodeURIComponent(p.account_id)}/roles`, { role });
      setMsg(`${p.name} is now ${LABEL[role] ?? role}.`);
      void load();
    } catch (e) {
      setMsg(e instanceof ApiError ? e.message : "That could not be saved. Please try again.");
    }
  };
  return (
    <section aria-label="Roles">
      <h2 style={{ fontSize: 16 }}>Roles</h2>
      <table className="ds-table">
        <thead><tr><th>Person</th><th>Role</th></tr></thead>
        <tbody>{data.people.map((p) => (
          <tr key={p.account_id}>
            <td>{p.name}</td>
            <td>
              <select className="ds-input" aria-label={`Role of ${p.name}`} value={data.choices.find((c) => p.roles.includes(c)) ?? ""}
                onChange={(e) => void change(p, e.target.value)}>
                {data.choices.map((c) => <option key={c} value={c}>{LABEL[c] ?? c}</option>)}
              </select>
              {p.roles.includes("head_of_data") ? <span className="ds-muted"> and head of data</span> : null}
            </td>
          </tr>
        ))}</tbody>
      </table>
      {msg ? <p role="status">{msg}</p> : null}
    </section>
  );
}
