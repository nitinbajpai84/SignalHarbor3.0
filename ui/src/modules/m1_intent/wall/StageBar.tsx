import { useEffect, useState } from "react";

import { ApiError } from "../../../api/client";
import { Button } from "../../../design";
import { closeRooms, getRoom, sendEveryone, startBriefing, startTogether } from "../api";
import { closesWhen, wallCopy as t } from "./copy";

const STAGES: [string, string][] = [
  ["lobby", "Lobby"], ["briefing", "Briefing"], ["private_rooms", "Private rooms"], ["board", "Wall"],
  ["together", "Together"], ["signing", "Signing"], ["closed", "Closed"],
];
// the next step from each stage, in plain words; later stages are run from their own screens
const NEXT: Record<string, [string, (id: string) => Promise<unknown>]> = {
  lobby: ["Start the briefing", startBriefing],
  briefing: ["Open the private rooms", sendEveryone],
  private_rooms: ["Close the rooms and bring everyone to the wall", closeRooms],
  board: ["Close the wall", startTogether],
};

/** The organiser's stage bar: the stages in order, the ones behind and the current one lit, one button for the next step behind "Are you sure?". */
/** `closes` comes from the wall, which already loaded the board: the bar never fetches the board itself. */
export default function StageBar({ sessionId, closes = null }: { sessionId: string; closes?: string | null }) {
  const [state, setState] = useState<string | null>(null);
  const [organiser, setOrganiser] = useState(false);
  const [sure, setSure] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  useEffect(() => {
    getRoom(sessionId).then((r) => { setState(r.state); setOrganiser(r.organiser); }).catch(() => undefined);
  }, [sessionId]);

  if (state === null || !organiser) return null; // a participant sees LIVE and the closing time in the wall head, as the canvas shows
  const next = organiser ? NEXT[state] : undefined;
  const at = STAGES.findIndex(([id]) => id === state);
  const go = async () => {
    try {
      await next![1](sessionId);
      window.location.reload();
    } catch (e) {
      setSure(false);
      setProblem(e instanceof ApiError ? e.message : t.failed);
    }
  };
  const when = closesWhen(closes, "long");

  return (
    <nav aria-label={t.stagesLabel} className="ds-card ds-stagebar">
      <ol className="ds-stagebar__stages">
        {STAGES.map(([id, label], i) => (
          <li key={id} aria-current={i === at ? "step" : undefined}
            className={`ds-stagebar__stage${i === at ? " ds-stagebar__stage--now" : i < at ? " ds-stagebar__stage--done" : ""}`}>{label}</li>
        ))}
      </ol>
      {when ? <p className="ds-stagebar__when">{t.closesLine(when)}</p> : null}
      {next && !sure ? <Button variant="primary" onClick={() => setSure(true)}>{next[0]}</Button> : null}
      {next && sure ? (
        <div role="alertdialog" aria-label={t.sure} className="ds-stagebar__sure">
          <span>{t.sure}</span>
          <Button variant="primary" onClick={() => void go()}>{t.yes}</Button>
          <Button onClick={() => setSure(false)}>{t.no}</Button>
        </div>
      ) : null}
      {problem ? <p role="alert" className="ds-stagebar__problem">{problem}</p> : null}
    </nav>
  );
}
