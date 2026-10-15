import CharterPaper from "../CharterPaper";
import { getCharter, type CharterPage } from "../api";
import { m1Charter as T } from "../copy";
import { useLoad } from "../useLoad";

/** The charter, read-only, for a seated guest once the session has closed: the signed result, no buttons. Shows nothing when there is none. */
export default function ClosedCharter({ sessionId }: { sessionId: string }) {
  const { data } = useLoad<CharterPage>(() => getCharter(sessionId), `closed-charter:${sessionId}`);
  const c = data?.charter;
  if (!c) return null;
  return (
    <CharterPaper doc={c} status={c.status}>
      <p className="n-e1-def-note">{T.readOnlyGuest}</p>
    </CharterPaper>
  );
}
