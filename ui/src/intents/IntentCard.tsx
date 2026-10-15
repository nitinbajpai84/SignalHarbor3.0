import type { CSSProperties } from "react";
import { Link } from "react-router-dom";

import { Pill } from "../design";
import AffectsYouChip from "./AffectsYouChip";
import { homeCopy as t } from "./intentHomeCopy";

/** One intent as the home shows it: every field is worked out on the server for this viewer (GET /api/intents/home). */
export interface HomeCard {
  id: string;
  type: string;
  type_name: string;
  title: string;
  state: string;
  stage: string;
  days: string;
  days_warn: boolean;
  organiser: string;
  people: string;
  your_role: string | null;
  mine: boolean;
  affects_you?: boolean;
  extended: boolean;
  extended_note: string;
  areas: string[];
  href: string;
}

/** One colour per type, always with the word (spec 04, Type chip). */
const TYPE_COLOUR: Record<string, string> = {
  initiative: "var(--ds-teal)", brainstorm: "#8b7cf6", pulse: "#4aa3df", problem: "var(--ds-amber)", decision: "#d16ba5",
};

export function TypeChip({ type, name }: { type: string; name: string }) {
  const c = TYPE_COLOUR[type] ?? "var(--ds-ink-muted)";
  return <span className="ds-chip" style={{ borderColor: c, color: c, padding: "2px 8px", fontSize: 14 }}>{name}</span>;
}

const CARD: CSSProperties = { display: "flex", flexDirection: "column", gap: 6, padding: 14, color: "var(--ds-ink)", textDecoration: "none", minWidth: 0 };
const TITLE: CSSProperties = { display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden", fontSize: 15 };
const ROW: CSSProperties = { display: "flex", flexWrap: "wrap", gap: 6, alignItems: "center" };

function StatePill({ state }: { state: string }) {
  if (state === "open") return null;
  const tone = state === "draft" ? "draft" : state === "closing" ? "late" : "open";
  return <Pill tone={tone}>{t.stateNames[state] ?? state}</Pill>;
}

export default function IntentCard({ card, alsoIn, area }: { card: HomeCard; alsoIn?: string | null; area?: string }) {
  const label = `${card.title}, ${card.type_name}, ${card.stage}, ${card.days}`;
  return (
    <Link to={card.href} className="ds-card" style={CARD} aria-label={label}>
      <div style={ROW}>
        <TypeChip type={card.type} name={card.type_name} />
        <StatePill state={card.state} />
        {card.your_role && <span className="ds-chip ds-chip--active" style={{ padding: "2px 8px", fontSize: 14 }} title={t.yourRole}>{card.your_role}</span>}
        <AffectsYouChip affected={!!card.affects_you} area={area} />
        {card.extended && <span className="ds-chip" style={{ padding: "2px 8px", fontSize: 14 }} title={card.extended_note} tabIndex={0}>{t.extended}</span>}
      </div>
      <strong style={TITLE}>{card.title}</strong>
      <span className="ds-soft">{card.stage}</span>
      <span className={card.days_warn ? "ds-warn" : "ds-soft"}>{card.days}</span>
      <span className="ds-soft" style={{ fontSize: 13 }}>{card.organiser} · {card.people}</span>
      {alsoIn && <span className="ds-muted" style={{ fontSize: 14 }}>{t.alsoIn(alsoIn)}</span>}
    </Link>
  );
}
