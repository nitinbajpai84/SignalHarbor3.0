import { useEffect, useState } from "react";

import { ROLES, declineOwner, getWorkList, putOwners, type KpiFull, type Role, type WorkList } from "../api";
import { m2Work } from "../copy";
import ProvCell from "./ProvCell";
import { S } from "./layout";

interface Props {
  id: string;
  kpi: KpiFull;
  me: string;
  locked: boolean;
  act: (p: Promise<WorkList>) => void;
}

type People = NonNullable<WorkList["people"]>;

function OwnerRow({ id, kpi, role, locked, act, people }: Omit<Props, "me"> & { role: Role; people: People }) {
  const o = kpi.owners[role];
  const [name, setName] = useState("");
  const [picked, setPicked] = useState("");
  const [account, setAccount] = useState(false);
  const label = m2Work.roles[role];
  return (
    <li style={S.owner}>
      <div>
        <strong>{label}</strong>
        <div className="n-muted">{m2Work.roleHelp[role]}</div>
      </div>
      {o.mark === "unknown" ? (
        <div>
          <div className="n-muted">{o.from.startsWith("declined") ? m2Work.declinedBy(o.from.replace("declined by ", "")) : m2Work.noOwner}</div>
          {people.length > 0 ? (
            <select className="n-input" aria-label={`${label}: ${m2Work.pickPerson}`} value={picked} disabled={locked} onChange={(e) => setPicked(e.target.value)}>
              <option value="">{m2Work.pickNobody}</option>
              {people.map((p) => (
                <option key={p.account_id} value={p.account_id}>
                  {p.display_name}
                </option>
              ))}
            </select>
          ) : null}
          <div className="n-flex wrap">
            <input className="n-input" aria-label={`${label}: ${m2Work.ownerName}`} placeholder={people.length > 0 ? m2Work.orTypeName : m2Work.ownerName} value={name} disabled={locked || picked !== ""} onChange={(e) => setName(e.target.value)} />
            <label className="n-flex">
              <input type="checkbox" checked={account} disabled={locked} onChange={(e) => setAccount(e.target.checked)} /> {m2Work.hasAccount}
            </label>
            <button type="button" className="n-btn sm" disabled={locked || (!picked && !name.trim())} aria-label={`${m2Work.nominate}: ${label}`}
              onClick={() => act(putOwners(id, kpi.id, { [role]: picked ? { account_id: picked } : { name, has_account: account } }))}>
              {m2Work.nominate}
            </button>
          </div>
        </div>
      ) : (
        <div>
          <ProvCell p={o} />
          <div className="n-flex wrap">
            <button type="button" className="n-btn sm ghost" disabled={locked} aria-label={`${m2Work.declineOwner}: ${label}`} onClick={() => act(declineOwner(id, kpi.id, role))}>
              {m2Work.declineOwner}
            </button>
            <button type="button" className="n-btn sm ghost" disabled={locked} aria-label={`${m2Work.withdraw}: ${label}`} onClick={() => act(putOwners(id, kpi.id, { [role]: { name: "", has_account: false } }))}>
              {m2Work.withdraw}
            </button>
          </div>
        </div>
      )}
    </li>
  );
}

/** M2-04: the business, data and process owner, each a named person with or without an account. One person may be all three. */
export default function OwnersPanel({ id, kpi, me, locked, act }: Props) {
  const [people, setPeople] = useState<People>([]);
  useEffect(() => {
    let live = true;
    getWorkList(id)
      .then((w) => live && setPeople(w.people ?? []))
      .catch(() => undefined); // no list to pick from: a typed name still works
    return () => {
      live = false;
    };
  }, [id]);
  return (
    <div>
      <h3 style={S.h3}>{m2Work.ownersTitle}</h3>
      {kpi.missing_owners.length > 0 ? (
        <p className="n-muted">{m2Work.missingOwners(kpi.missing_owners.map((r) => m2Work.roles[r].toLowerCase()).join(", "))}</p>
      ) : null}
      <ul style={S.list}>
        {ROLES.map((r) => (
          <OwnerRow key={`${r}-${kpi.owners[r].at}`} id={id} kpi={kpi} role={r} locked={locked} act={act} people={people} />
        ))}
      </ul>
      {me ? (
        <button type="button" className="n-btn sm" disabled={locked} onClick={() => {
          const mine = { name: me, has_account: true };
          act(putOwners(id, kpi.id, { business: mine, data: mine, process: mine }));
        }}>
          {m2Work.meForAll}
        </button>
      ) : null}
    </div>
  );
}
