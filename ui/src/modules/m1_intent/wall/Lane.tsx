import Card, { type WallCard } from "./Card";
import { wallCopy as t } from "./copy";

export const SHOWN = 6;

/** One lane: heading, count, up to SHOWN cards and "+ n more". The projector view shows the heading and count only. */
export default function Lane({ id, cards, projector, onPickUp, onHide, onUndo }: {
  id: WallCard["lane"]; cards: WallCard[]; projector: boolean; onPickUp?: (id: string) => Promise<void>; onHide?: (id: string) => Promise<void>; onUndo?: (id: string) => Promise<void>;
}) {
  const l = t.lanes[id];
  return (
    <section aria-label={l.name} className={`ds-card ds-wall-lane ds-wall-lane--${id}`}>
      <h3 className="ds-wall-lane__head">
        {l.name} <span className="ds-wall-lane__count" data-testid={`count-${id}`}>{cards.length}</span>
      </h3>
      <p className="ds-wall-lane__line">{l.line}</p>
      {projector ? null : (
        <ul className="ds-wall-lane__cards">
          {cards.length === 0 ? <li className="ds-wall-lane__empty">{t.emptyLane}</li> : null}
          {cards.slice(0, SHOWN).map((c) => <Card key={c.id} card={c} onPickUp={onPickUp} onHide={onHide} onUndo={onUndo} />)}
          {cards.length > SHOWN ? <li className="ds-wall-lane__more">{t.more(cards.length - SHOWN)}</li> : null}
        </ul>
      )}
    </section>
  );
}
