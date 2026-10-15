import { useParams } from "react-router-dom";

import ScreenState from "../../../components/ScreenState";
import { getBoard, pGet, sessionPath, type RoomView } from "../api";
import { m1Board as t } from "../copy";
import ClosedCharter from "../charter/ClosedCharter";
import { SummaryLink } from "../summary/SummaryScreen";
import TogetherScreen from "../together/TogetherScreen";
import BoardScreen from "./BoardScreen";
import { problemText, usePolled } from "./usePolled";

/**
 * The stages after the private rooms, on one page: the board while the rooms close and North groups, then back in the
 * room. It follows the session's own stage, so a person never has to choose between the two addresses. A participant's
 * page (the join page) can mount this with the session id and nothing else.
 */
export default function LaterStages({ sessionId: given }: { sessionId?: string } = {}) {
  const params = useParams();
  const sessionId = given ?? params.sessionId ?? "";
  const room = usePolled(() => pGet<RoomView>(sessionId, `${sessionPath(sessionId)}/lobby`), `stage:${sessionId}`);
  const stage = room.data?.state;
  return (
    <ScreenState state={room.state} onRetry={room.reload} message={room.state === "error" ? problemText(room.failure) || t.loadFailed : undefined}>
      {stage === "closed" ? (
        <>
          <TogetherScreen sessionId={sessionId} />
          <ClosedCharter sessionId={sessionId} />
          <SummaryLink sessionId={sessionId} />
        </>
      ) : stage === "together" || stage === "signing" ? (
        <TogetherScreen sessionId={sessionId} />
      ) : stage === "paused" ? (
        <HeldRoom sessionId={sessionId} />
      ) : stage ? (
        <BoardScreen sessionId={sessionId} onTogether={room.reload} />
      ) : null}
    </ScreenState>
  );
}

/** A held session shows the stage it was held at. */
function HeldRoom({ sessionId }: { sessionId: string }) {
  const probe = usePolled(() => getBoard(sessionId), `held:${sessionId}`);
  const from = probe.data?.paused_from;
  if (probe.state === "loading") return <ScreenState state="loading" />;
  return from === "together" || from === "signing" ? <TogetherScreen sessionId={sessionId} /> : <BoardScreen sessionId={sessionId} />;
}
