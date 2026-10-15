import { Chip } from "../design";
import { affectedCopy as t } from "./affectedCopy";

/** The "Affects you" chip (spec 47, screen B). Shown only to a person who is affected and holds no stronger role; the card is the link. */
export default function AffectsYouChip({ affected, stronger = false, area }: { affected: boolean; stronger?: boolean; area?: string }) {
  if (!affected || stronger) return null;
  return (
    <span title={area ? t.chipBecause(area) : undefined}>
      <Chip>{t.chip}</Chip>
    </span>
  );
}
