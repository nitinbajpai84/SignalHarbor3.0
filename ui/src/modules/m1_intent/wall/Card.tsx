import { useEffect, useState } from "react";

import { Button } from "../../../design";
import { wallCopy as t } from "./copy";

export interface WallCard {
  id: string;
  lane: "intent" | "pain_point" | "future_signal" | "lever";
  text: string;
  anonymous: boolean;
  author?: string;
  mine: boolean;
  /** How many of the four questions are answered; null when the server does not say. */
  quarters: number | null;
  guessed: number;
  sealed: boolean;
  area?: string;
  /** Set on a suggestion from North: the document it came from. */
  suggestionFrom?: string;
  /** The person's own card not yet on the wall (North's draft or one they have not put up). */
  draft?: boolean;
  /** Someone else's card while the rooms are open: a silhouette, no words. */
  other?: boolean;
}

const words = {
  other: "Someone's card",
  otherFoot: "Words show when the rooms close",
  draft: "Draft, only you see it",
  notThisOne: "Not this one",
  undo: "Undo",
  hidden: "Hidden. North will not offer it to you again.",
  hideError: "That could not be hidden. Try again.",
};
/** UNDO_MS: how long Undo is offered after "Not this one"; it does not survive a refresh (file 25, open question 6). */
export const UNDO_MS = 8000;
/** The foot shows initials, never the name; a value that is already initials stays as it is. */
export const initialsOf = (a: string): string =>
  /^[A-Z]{1,3}$/.test(a) ? a : a.split(/[^A-Za-z0-9]+/).filter(Boolean).slice(0, 2).map((w) => w[0]).join("").toUpperCase();

/** The left edge is a column of four segments, filled from the bottom: the first n are on, in the lane's colour. */
function Edge({ n }: { n: number }) {
  return (
    <div aria-hidden="true" data-testid="edge" data-filled={n} className="ds-wall-edge">
      {[0, 1, 2, 3].map((i) => <span key={i} className={`ds-wall-edge__seg${i < n ? " ds-wall-edge__seg--on" : ""}`} />)}
    </div>
  );
}

export default function Card({ card, onPickUp, onHide, onUndo }: {
  card: WallCard; onPickUp?: (id: string) => Promise<void>; onHide?: (id: string) => Promise<void>; onUndo?: (id: string) => Promise<void>;
}) {
  const q = card.quarters === null ? 0 : Math.max(0, Math.min(4, card.quarters));
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // "Not this one": the card fades to a one-line Undo for a short time, then goes
  const [hidden, setHidden] = useState<"shown" | "undo" | "gone">("shown");
  useEffect(() => {
    if (hidden !== "undo") return;
    const t0 = setTimeout(() => setHidden("gone"), UNDO_MS);
    return () => clearTimeout(t0);
  }, [hidden]);
  const act = async (fn: (id: string) => Promise<void>, then: "undo" | "shown", fail: string) => {
    if (loading) return;
    setLoading(true);
    setError(null);
    try {
      await fn(card.id);
      setHidden(then);
    } catch {
      setError(fail);
    }
    setLoading(false);
  };

  const handlePickUp = async () => {
    if (!onPickUp || loading) return;
    setLoading(true);
    setError(null);
    try {
      await onPickUp(card.id);
    } catch {
      setError(t.pickUpError);
      setLoading(false);
    }
  };

  if (card.other) {
    return (
      <li className="ds-wall-card ds-wall-card--sealed" data-kind="other">
        <div className="ds-wall-card__body">
          <p className="ds-wall-card__text">{words.other}</p>
          <small className="ds-wall-card__foot">{words.otherFoot}</small>
        </div>
      </li>
    );
  }
  // sealed: a striped silhouette; the card's own words, author, quarters and source never reach the page
  if (card.sealed) {
    return (
      <li className="ds-wall-card ds-wall-card--sealed" data-kind="sealed">
        <div className="ds-wall-card__body">
          <p className="ds-wall-card__text">{t.sealed(card.area ?? t.sealedArea)}</p>
          <small className="ds-wall-card__foot">{t.sealedLabel}</small>
        </div>
      </li>
    );
  }
  if (card.suggestionFrom !== undefined && hidden === "gone") return null;
  if (card.suggestionFrom !== undefined && hidden === "undo") {
    return (
      <li className="ds-wall-card ds-wall-card--suggestion" data-kind="suggestion-hidden" style={{ opacity: 0.7 }}>
        <div className="ds-wall-card__body">
          <small>{words.hidden}</small>
          {error ? <small className="ds-wall-card__error" role="alert">{error}</small> : null}
          <Button disabled={loading || !onUndo} onClick={() => void act(onUndo!, "shown", t.pickUpError)}>{words.undo}</Button>
        </div>
      </li>
    );
  }
  if (card.suggestionFrom !== undefined) {
    return (
      <li className="ds-wall-card ds-wall-card--suggestion" data-kind="suggestion">
        <div className="ds-wall-card__body">
          <p className="ds-wall-card__text">{card.text}</p>
          <small className="ds-wall-card__from">{t.suggestedBy(card.suggestionFrom)}</small>
          {error ? <small className="ds-wall-card__error" role="alert">{error}</small> : null}
          <div style={{ display: "flex", gap: "var(--ds-s2)", flexWrap: "wrap" }}>
            <Button disabled={!onPickUp || loading} onClick={() => void handlePickUp()}>{loading ? t.pickingUp : t.pickUp}</Button>
            {onHide ? <Button disabled={loading} onClick={() => void act(onHide, "undo", words.hideError)}>{words.notThisOne}</Button> : null}
          </div>
        </div>
      </li>
    );
  }
  return (
    <li className={`ds-wall-card${card.draft ? " ds-wall-card--suggestion" : ""}`} data-kind={card.draft ? "draft" : "card"}>
      <Edge n={q} />
      <div className="ds-wall-card__body">
        <p className="ds-wall-card__text">{card.text}</p>
        {/* an anonymous card never carries a name or an initial */}
        <small className="ds-wall-card__foot">
          {card.draft ? `${words.draft} · ` : ""}{card.anonymous ? t.anonymous : card.author ? initialsOf(card.author) : card.mine ? t.you : t.anonymous}
          {card.quarters !== null || card.guessed > 0 ? (
            <span className="ds-wall-card__q">
              {card.quarters !== null ? t.answered(q) : ""}
              {card.guessed > 0 ? ` ${t.guessed(card.guessed)}` : ""}
            </span>
          ) : null}
        </small>
      </div>
    </li>
  );
}
