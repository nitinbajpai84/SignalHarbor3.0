// One date style everywhere, independent of the viewer's locale and time zone: "9 Oct 2026", "09:12", "9 Oct 2026, 09:12".
// PF2: every instant is shown in the company's one time zone (company profile, default Asia/Singapore), set once from the session.
// A bare date (YYYY-MM-DD) is a calendar day, not an instant, and a stamp without an offset is already company time: both read as written.
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const p2 = (n: number) => String(n).padStart(2, "0");
export const DEFAULT_ZONE = "Asia/Singapore";
let zone = DEFAULT_ZONE;
let fmt: Intl.DateTimeFormat | null = null;

/** Set the company's time zone (from /api/auth/me). An empty or unknown name keeps the default. */
export const setCompanyZone = (tz: string | null | undefined): void => {
  try {
    fmt = new Intl.DateTimeFormat("en-GB", { timeZone: tz || DEFAULT_ZONE, year: "numeric", month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit", hourCycle: "h23" });
    zone = tz || DEFAULT_ZONE;
  } catch { /* unknown zone name: keep the one we had */ }
};
export const companyZone = () => zone;

type Parts = { y: number; m: number; d: number; h?: number; mi?: number };
const AS_WRITTEN = /^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2})(?::\d{2}(?:\.\d+)?)?)?$/;
const parse = (iso: string | null | undefined): Parts | null => {
  if (!iso) return null;
  const w = AS_WRITTEN.exec(iso);
  if (w) return { y: Number(w[1]), m: Number(w[2]), d: Number(w[3]), ...(w[4] ? { h: Number(w[4]), mi: Number(w[5]) } : {}) };
  const t = new Date(iso);
  if (Number.isNaN(t.getTime())) return null;
  if (!fmt) setCompanyZone(zone);
  const o = Object.fromEntries(fmt!.formatToParts(t).map((x) => [x.type, x.value]));
  return { y: Number(o.year), m: Number(o.month), d: Number(o.day), h: Number(o.hour) % 24, mi: Number(o.minute) };
};
const dmy = (p: Parts) => `${p.d} ${MONTHS[p.m - 1]} ${p.y}`;
const hm = (p: Parts) => `${p2(p.h!)}:${p2(p.mi!)}`;

/** "9 Oct 2026"; `none` when the value is empty or not a date. */
export const day = (iso: string | null | undefined, none = ""): string => { const p = parse(iso); return p ? dmy(p) : none; };
/** "09:12"; a bare date has no time of day, so `none`. */
export const time = (iso: string | null | undefined, none = ""): string => { const p = parse(iso); return p && p.h !== undefined ? hm(p) : none; };
/** "9 Oct 2026, 09:12"; a bare date has no time of day, so it reads as the date alone. */
export const when = (iso: string | null | undefined, none = ""): string => {
  const p = parse(iso);
  return p ? (p.h === undefined ? dmy(p) : `${dmy(p)}, ${hm(p)}`) : none;
};
