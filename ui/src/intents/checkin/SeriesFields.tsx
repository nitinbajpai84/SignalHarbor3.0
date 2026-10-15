import { useEffect, useState } from "react";

import { Button, Chip } from "../../design";
import { days, startCopy as t } from "./checkinCopy";

export interface Person { id: string | null; name: string; role: string | null; tagged: boolean; has_account: boolean }
export interface Preview { opens: string; answers_close: string; review_day: string; closes: string; next_opens: string; weekday: string }
export interface Setup {
  areas: { id: string; name: string; kind: string }[]; people: Person[]; minimum: number; extra_max: number;
  area: string | null; reporters: string[]; close_day: string; reviewer: string; preview: Preview;
}
export interface Values { area: string | null; reporters: string[]; close_day: string; reviewer: string; extra: string }

/** True below 700 px, where the phone layout of file 17 applies. */
export function usePhone(): boolean {
  const q = typeof window !== "undefined" && window.matchMedia ? window.matchMedia("(max-width: 700px)") : null;
  const [phone, setPhone] = useState(!!q?.matches);
  useEffect(() => {
    if (!q) return;
    const on = () => setPhone(q.matches);
    q.addEventListener("change", on);
    return () => q.removeEventListener("change", on);
  }, [q]);
  return phone;
}

export function AreaPick({ setup, value, onChange }: { setup: Setup; value: string | null; onChange: (a: string) => void }) {
  const [find, setFind] = useState("");
  if (setup.areas.length === 0) return <p className="ck-muted" role="status">{t.noAreas}</p>;
  const list = setup.areas.filter((a) => a.name.toLowerCase().includes(find.toLowerCase()));
  return (
    <div className="ck-field">
      {setup.areas.length > 8 && <input type="text" aria-label={t.q1} value={find} onChange={(e) => setFind(e.target.value)} />}
      <div className="ck-row" role="radiogroup" aria-label={t.q1}>
        {list.map((a) => <span key={a.id} role="radio" aria-checked={value === a.name}><Chip tone={value === a.name ? "active" : "default"} onClick={() => onChange(a.name)}>{a.name}</Chip></span>)}
      </div>
    </div>
  );
}

export function PeoplePick({ setup, area, value, onChange }: { setup: Setup; area: string | null; value: string[]; onChange: (v: string[]) => void }) {
  const tagged = setup.people.filter((p) => p.tagged && p.id);
  const toggle = (id: string) => onChange(value.includes(id) ? value.filter((x) => x !== id) : [...value, id]);
  return (
    <div className="ck-field">
      <p className="ck-muted">{t.people(value.length)}{value.length < setup.minimum ? `. ${t.minPeople(setup.minimum)}` : ""}</p>
      <div className="ck-row">
        {setup.people.map((p) => (
          <Chip key={p.name} tone={p.id && value.includes(p.id) ? "active" : "default"} onClick={p.id ? () => toggle(p.id as string) : undefined}>
            {p.name}{p.role ? `, ${p.role}` : ""}{p.id ? "" : ` (${t.noSignIn})`}
          </Chip>
        ))}
      </div>
      {area && (tagged.length > 0
        ? <div><Button onClick={() => onChange(tagged.map((p) => p.id as string))}>{t.everyone(tagged.length, area)}</Button></div>
        : <p className="ck-muted">{t.noneTagged}</p>)}
    </div>
  );
}

/** Question 3: the close day and the reviewer. */
export function DayReviewer({ setup, v, set }: { setup: Setup; v: Values; set: (p: Partial<Values>) => void }) {
  return (
    <>
      <div className="ck-field">
        <label htmlFor="ck-day">{t.q3}</label>
        <select id="ck-day" value={v.close_day} onChange={(e) => set({ close_day: e.target.value })}>
          {Object.entries(days).map(([k, n]) => <option key={k} value={k}>{n}</option>)}
        </select>
      </div>
      <div className="ck-field">
        <label htmlFor="ck-rev">{t.q3b}</label>
        <select id="ck-rev" value={v.reviewer} onChange={(e) => set({ reviewer: e.target.value })}>
          {setup.people.filter((p) => p.id).map((p) => <option key={p.id} value={p.id as string}>{p.name}</option>)}
        </select>
      </div>
    </>
  );
}

/** Question 4: the three fixed lines and the one optional question of your own. */
export function OwnQuestion({ setup, v, set }: { setup: Setup; v: Values; set: (p: Partial<Values>) => void }) {
  const [open, setOpen] = useState(!!v.extra);
  return (
    <div className="ck-field">
      <ul className="ck-list">
        <li>What ran well this week? <span className="ck-tag">ran</span></li>
        <li>What broke or nearly broke? <span className="ck-tag">broke</span></li>
        <li>What is on your mind? <span className="ck-tag">thought</span></li>
        {v.extra && <li>{v.extra} <span className="ck-muted">({t.q4Note})</span></li>}
      </ul>
      {open
        ? <input type="text" aria-label={t.q4Add} maxLength={setup.extra_max} placeholder={t.q4Add} value={v.extra} onChange={(e) => set({ extra: e.target.value })} />
        : <div><Button onClick={() => setOpen(true)}>{t.q4Add}</Button></div>}
    </div>
  );
}

export const previewLine = (p: Preview | undefined, d: (s: string) => string): string =>
  p ? t.preview(d(p.opens), d(p.closes), d(p.answers_close), d(p.review_day), d(p.closes), p.weekday) : t.previewNa;
