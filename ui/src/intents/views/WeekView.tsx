import { useParams, useSearchParams } from "react-router-dom";

import { PageFrame } from "../../design";
import { EventsLink } from "./EventsView";
import { MineView, RecordView } from "../checkin/WeekHistory";
import SeriesHome from "../checkin/SeriesHome";
import WeekEntry from "../checkin/WeekEntry";

/** The Weekly check-in's two doors (specs 38 and 39). `/centre/intent/<id>` is the series home; `/week` is the reporter's entry, and
 *  `?view=mine` and `?view=record` are the person's history and the week's record (ruling 18). The review is `/review` (spec 40). */
export default function WeekView() {
  const { intentId = "", view } = useParams<{ intentId: string; view?: string }>();
  const [params] = useSearchParams();
  const sub = params.get("view");
  const body = view === undefined ? <SeriesHome intentId={intentId} />
    : sub === "mine" ? <MineView intentId={intentId} />
    : sub === "record" ? <RecordView intentId={intentId} />
    : <WeekEntry intentId={intentId} />;
  return <PageFrame title="Weekly check-in" crumbs="INTENT CENTRE">{body}<EventsLink intentId={intentId} /></PageFrame>;
}
