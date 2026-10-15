import { useState, type ButtonHTMLAttributes, type CSSProperties, type ReactNode } from "react";
import { Link } from "react-router-dom";

// The parts every artboard is made of. Styling lives in styles/design.css (classes ds-*); only computed values are inline.

export interface NavLink { label: string; href: string; active?: boolean }

export function TopBar({ product, company, links, person, role, initials, menu }: {
  product: string; company?: string; links: NavLink[]; person: string; role: string; initials?: string; menu?: ReactNode;
}) {
  return (
    <header className="ds-topbar">
      <div className="ds-topbar__mark" aria-hidden="true" />
      <strong className="ds-topbar__product">{product}</strong>
      {company && <span className="ds-topbar__chip">{company}</span>}
      <div className="ds-topbar__spacer" />
      <nav className="ds-topbar__nav" aria-label="Main">
        {links.map((l) => <Link key={l.href} to={l.href} aria-current={l.active ? "page" : undefined}>{l.label}</Link>)}
      </nav>
      <span className="ds-topbar__who">
        {initials && <span className="ds-avatar" aria-hidden="true">{initials}</span>}
        <span>{person} · {role}</span>
      </span>
      {menu}
    </header>
  );
}

/** Two columns, three with a left `rail` (the control panel); rail and aside stack around the main column below 900px (design.css). */
export function PageFrame({ title, subline, crumbs, actions, children, aside, rail }: {
  title: ReactNode; subline?: ReactNode; crumbs?: ReactNode; actions?: ReactNode; children: ReactNode; aside?: ReactNode; rail?: ReactNode;
}) {
  return (
    <main className="ds-frame">
      {rail && <div className="ds-frame__rail">{rail}</div>}
      <section className="ds-frame__main">
        {crumbs && <p className="ds-frame__crumbs">{crumbs}</p>}
        <div className="ds-frame__head">
          <div className="ds-frame__titles">
            <h1 className="ds-frame__title">{title}</h1>
            {subline && <p className="ds-frame__subline">{subline}</p>}
          </div>
          {actions && <div className="ds-frame__actions">{actions}</div>}
        </div>
        {children}
      </section>
      {aside && <aside className="ds-frame__aside">{aside}</aside>}
    </main>
  );
}

export type Tone = "teal" | "amber";

export function Strip({ label, tone = "teal", children }: { label: string; tone?: Tone; children: ReactNode }) {
  return (
    <div className={`ds-strip ds-strip--${tone}`}>
      <p className="ds-strip__label">{label}</p>
      {children}
    </div>
  );
}

/** The whole card is one link. `inset` is the row form used inside another card (the ops report). */
export function ActionCard({ icon, title, detail, due, action, href, tone = "teal", inset = false }: {
  icon: ReactNode; title: string; detail: string; due?: string; action: string; href: string; tone?: Tone; inset?: boolean;
}) {
  return (
    <Link to={href} className={`ds-action ds-action--${tone} ${inset ? "ds-action--inset" : "ds-card"}`}>
      <span className="ds-action__icon">{icon}</span>
      <span className="ds-action__body">
        <strong className="ds-action__title">{title}</strong>
        <span className="ds-action__detail">{detail}</span>
        {due && <span className="ds-action__due">{due}</span>}
      </span>
      <span className="ds-action__word">{action}</span>
    </Link>
  );
}

export function SideCard({ title, action, tone, note, children }: {
  title: string; action?: { label: string; href: string }; tone?: Tone; note?: string; children: ReactNode;
}) {
  return (
    <div className={`ds-card ds-side${tone ? ` ds-side--${tone}` : ""}`}>
      <div className="ds-side__head">
        <strong className="ds-side__title">{title}</strong>
        {action && <Link to={action.href} className="ds-side__action ds-link">{action.label}</Link>}
      </div>
      {children}
      {note && <p className="ds-side__note">{note}</p>}
    </div>
  );
}

export function Footnote({ children }: { children: ReactNode }) {
  return <p className="ds-footnote">{children}</p>;
}

export function StatGrid({ cols = 3, children }: { cols?: number; children: ReactNode }) {
  return <div className="ds-stat-grid" style={{ "--ds-cols": cols } as CSSProperties}>{children}</div>;
}

/** One figure on the Watch grid. `text` is a sentence in place of a number (the market brief); `bare` drops the card (ops report). */
export function StatCard({ label, value, note, tone = "soft", valueTone, href, text = false, bare = false }: {
  label: string; value: ReactNode; note?: string; tone?: "soft" | "warn" | "muted"; valueTone?: "warn"; href?: string; text?: boolean; bare?: boolean;
}) {
  const cls = `ds-stat ${bare ? "ds-stat--bare" : "ds-card"}`;
  const body = (
    <>
      <span className="ds-stat__label">{label}</span>
      <strong className={`ds-stat__value${text ? " ds-stat__value--text" : ""}${valueTone ? " ds-stat__value--warn" : ""}`}>{value}</strong>
      {note && <span className={`ds-stat__note${tone === "soft" ? "" : ` ds-stat__note--${tone}`}`}>{note}</span>}
    </>
  );
  return href ? <Link to={href} className={cls}>{body}</Link> : <div className={cls}>{body}</div>;
}

export type PillTone = "ok" | "late" | "failed" | "draft" | "signed" | "open" | "restricted";

export function Pill({ tone, children }: { tone: PillTone; children: ReactNode }) {
  return <span className={`ds-pill ds-pill--${tone}`}>{children}</span>;
}

/** A rounded filter or view chip. A link with href, a button with onClick, otherwise a label. */
export function Chip({ children, tone = "default", href, onClick }: { children: ReactNode; tone?: "default" | "active"; href?: string; onClick?: () => void }) {
  const cls = `ds-chip${tone === "active" ? " ds-chip--active" : ""}`;
  if (href) return <Link to={href} className={cls} aria-current={tone === "active" ? "page" : undefined}>{children}</Link>;
  if (onClick) return <button type="button" className={cls} aria-pressed={tone === "active"} onClick={onClick}>{children}</button>;
  return <span className={cls}>{children}</span>;
}

export function Button({ variant = "secondary", className, type = "button", ...rest }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" }) {
  return <button type={type} className={`ds-btn${variant === "primary" ? " ds-btn--primary" : ""}${className ? ` ${className}` : ""}`} {...rest} />;
}

function scale(values: number[], lo: number, hi: number): (v: number) => number {
  const min = Math.min(...values), max = Math.max(...values);
  const span = max - min || 1;
  return (v) => hi - ((v - min) / span) * (hi - lo);
}

export function Sparkline({ points, width = 120, height = 32, label = "Trend" }: { points: number[]; width?: number; height?: number; label?: string }) {
  const y = scale(points, 2, height - 2);
  const step = points.length > 1 ? (width - 4) / (points.length - 1) : 0;
  const coords = points.map((v, i) => `${2 + i * step},${y(v)}`).join(" ");
  return (
    <svg className="ds-spark" width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img" aria-label={label}>
      <polyline points={coords} />
    </svg>
  );
}

export interface PeriodValue { period: string; value: number }

export function LineChart({ points, width = 600, height = 200, label = "Line chart" }: { points: PeriodValue[]; width?: number; height?: number; label?: string }) {
  const PAD = 24, BOTTOM = 28;
  const y = scale(points.map((p) => p.value), 12, height - BOTTOM);
  const step = points.length > 1 ? (width - 2 * PAD) / (points.length - 1) : 0;
  const xy = points.map((p, i) => ({ ...p, x: PAD + i * step, y: y(p.value) }));
  return (
    <svg className="ds-line" width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img" aria-label={label}>
      <line className="ds-line__base" x1={PAD} x2={width - PAD} y1={height - BOTTOM + 6} y2={height - BOTTOM + 6} />
      <polyline points={xy.map((p) => `${p.x},${p.y}`).join(" ")} />
      {xy.map((p) => (
        <g key={p.period}>
          <circle cx={p.x} cy={p.y} r={3}><title>{`${p.period}: ${p.value}`}</title></circle>
          <text x={p.x} y={height - 6} textAnchor="middle">{p.period}</text>
        </g>
      ))}
    </svg>
  );
}

export interface Column { key: string; label: string }

export function DataTable({ columns, rows }: { columns: Column[]; rows: Record<string, ReactNode>[] }) {
  return (
    <div className="ds-card ds-table-wrap">
      <table className="ds-table">
        <thead><tr>{columns.map((c) => <th key={c.key} scope="col">{c.label}</th>)}</tr></thead>
        <tbody>
          {rows.map((r, i) => <tr key={i}>{columns.map((c) => <td key={c.key}>{r[c.key]}</td>)}</tr>)}
        </tbody>
      </table>
    </div>
  );
}

export function EmptyState({ title, lines, links = [] }: { title: string; lines: string[]; links?: { label: string; href: string }[] }) {
  return (
    <div className="ds-card ds-empty">
      <strong className="ds-empty__title">{title}</strong>
      {lines.map((l) => <p key={l}>{l}</p>)}
      {links.length > 0 && <div className="ds-empty__links">{links.map((l) => <Link key={l.href} to={l.href} className="ds-link">{l.label}</Link>)}</div>}
    </div>
  );
}

export interface TabItem { label: string; href: string; icon: ReactNode; active?: boolean }

/** Shown only under 480px (design.css). */
export function PhoneTabBar({ items }: { items: TabItem[] }) {
  return (
    <nav className="ds-tabbar" aria-label="Main">
      {items.map((t) => (
        <Link key={t.href} to={t.href} className="ds-tabbar__item" aria-current={t.active ? "page" : undefined}>{t.icon}{t.label}</Link>
      ))}
    </nav>
  );
}

export interface TrailStep { step: string; label?: string; ref?: string; by?: string; at?: string; href?: string }

const STEP_CAPTION: Record<string, string> = { asked: "Asked by", defined: "Defined in", supplied: "Supplied by", built: "Built by", released: "Released" };
const STEP_ORDER = ["asked", "defined", "supplied", "built", "released"];

/** The five-step provenance on the Node artboard. A step with no record reads "Not yet". */
export function Trail({ steps }: { steps: TrailStep[] }) {
  const extra = steps.filter((s) => !STEP_ORDER.includes(s.step)).map((s) => s.step);
  return (
    <div className="ds-trail">
      {[...STEP_ORDER, ...extra].map((name) => {
        const s = steps.find((x) => x.step === name);
        const cap = STEP_CAPTION[name] ?? name.charAt(0).toUpperCase() + name.slice(1);
        const detail = s ? [s.ref, s.by, s.at].filter(Boolean).join(" · ") : "";
        const cls = `ds-trail__step${s ? "" : " ds-trail__step--empty"}`;
        const body = (
          <>
            <span className="ds-trail__cap">{cap}</span>
            <strong>{s?.label ?? "Not yet"}</strong>
            {detail && <span className="ds-trail__detail">{detail}</span>}
          </>
        );
        return s?.href
          ? <Link key={name} to={s.href} className={`${cls} ds-trail__step--link`}>{body}</Link>
          : <div key={name} className={cls}>{body}</div>;
      })}
    </div>
  );
}

export interface Version { v: number; what: string; by: string; at: string }

export function VersionList({ versions }: { versions: Version[] }) {
  const sorted = [...versions].sort((a, b) => b.v - a.v);
  return (
    <div className="ds-versions">
      {sorted.map((v, i) => (
        <div key={v.v} className={`ds-versions__row${i === 0 ? " ds-versions__row--current" : ""}`}>
          <span className="ds-versions__v">v{v.v}</span>
          <span>{[v.what, v.by === "Lens" ? "" : v.by, v.at].filter(Boolean).join(" · ")}</span>
        </div>
      ))}
    </div>
  );
}

export interface Comment {
  id: string; kind: "comment" | "suggestion" | "ambiguity"; text: string; by: string; at: string;
  state: string; decided_by: string | null; answer: string | null;
  /** The route's own state line ("Open · Olga to decide · Lens drafted an answer"); shown as is when present. */
  line?: string | null;
}

const KIND_VERB: Record<Comment["kind"], string> = { comment: "commented", suggestion: "suggested a change", ambiguity: "flagged an ambiguity" };

function initialsOf(name: string): string {
  return name.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w.charAt(0).toUpperCase()).join("");
}

function stateLine(c: Comment): string {
  if (c.line) return c.line;
  if (c.state === "open") return "Open";
  const head = c.state.charAt(0).toUpperCase() + c.state.slice(1);
  return `${head}${c.decided_by ? ` by ${c.decided_by}` : ""}${c.answer ? `: ${c.answer}` : ""}`;
}

/** Comments on a thing on the map. The decide row shows only when canDecide and onDecide are given. */
export function CommentThread({ comments, canDecide, onDecide }: {
  comments: Comment[]; canDecide: boolean; onDecide?: (id: string, state: "accepted" | "declined" | "answered", answer: string) => void;
}) {
  const [answers, setAnswers] = useState<Record<string, string>>({});
  return (
    <div className="ds-thread">
      {comments.map((c) => (
        <div key={c.id} className="ds-comment">
          <span className="ds-avatar" aria-hidden="true">{initialsOf(c.by)}</span>
          <div className="ds-comment__body">
            <span><b>{c.by}</b> {KIND_VERB[c.kind]} · {c.at}</span>
            <span className="ds-comment__text">"{c.text}"</span>
            <span className={`ds-comment__state${c.state === "open" ? " ds-comment__state--open" : ""}`}>{stateLine(c)}</span>
            {canDecide && onDecide && c.state === "open" && (
              <div className="ds-comment__decide">
                <input aria-label={`Answer to ${c.by}`} value={answers[c.id] ?? ""} onChange={(e) => setAnswers({ ...answers, [c.id]: e.target.value })} />
                {c.kind === "suggestion" && <Button variant="primary" onClick={() => onDecide(c.id, "accepted", answers[c.id] ?? "")}>Accept</Button>}
                {c.kind === "suggestion" && <Button onClick={() => onDecide(c.id, "declined", answers[c.id] ?? "")}>Decline</Button>}
                <Button onClick={() => onDecide(c.id, "answered", answers[c.id] ?? "")}>Answer</Button>
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

export function Signature({ state, by, at, onSign }: { state: "waiting" | "signed"; by?: string; at?: string; onSign?: () => void }) {
  return (
    <div className="ds-card ds-signature">
      <Pill tone={state === "signed" ? "signed" : "draft"}>{state === "signed" ? "Signed" : "Not signed"}</Pill>
      <span className="ds-signature__text">
        {state === "signed" ? [by && `Signed by ${by}`, at].filter(Boolean).join(" · ") : by ? `Waiting for ${by}` : "Waiting for a signature"}
      </span>
      {state === "waiting" && onSign && <Button variant="primary" onClick={onSign}>Sign</Button>}
    </div>
  );
}

export function RoomTile({ number, name, state, line, counts, action }: {
  number: number; name: string; state: "open" | "next" | "dim"; line: string; counts: (string | { text: string; tone: Tone })[]; action?: { label: string; href: string };
}) {
  return (
    <div className={`ds-card ds-room ds-room--${state}`}>
      <div className="ds-room__head">
        <span className="ds-room__n">{number}</span>
        <strong className="ds-room__name">{name}</strong>
      </div>
      <p className="ds-room__line">{line}</p>
      {counts.length > 0 && (
        <span className="ds-room__counts">
          {counts.map((c, i) => (
            <span key={i}>{i > 0 && " · "}{typeof c === "string" ? c : <span className={`ds-room__count--${c.tone}`}>{c.text}</span>}</span>
          ))}
        </span>
      )}
      {action && <Link to={action.href} className="ds-room__action ds-link">{action.label}</Link>}
    </div>
  );
}
