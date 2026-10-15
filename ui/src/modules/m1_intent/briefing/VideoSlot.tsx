import { useEffect, useState } from "react";

import Panel from "../../../components/Panel";
import { getBriefingVideo, type BriefingView } from "../api";
import { m1Briefing } from "../copy";

/**
 * The briefing video slot (M1-06). A video from the company's own space plays here; with none, a placeholder card
 * holds the place (a real file replaces it later). The written rules are always shown beside it by the screen.
 * The file is fetched with the person's own token (a guest has no cookie, and a <video> tag cannot send a header),
 * then played from a blob address.
 */
function FileVideo({ sessionId }: { sessionId: string }) {
  const [src, setSrc] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let url: string | null = null;
    let live = true;
    void getBriefingVideo(sessionId).then((blob) => {
      if (!live) return;
      if (!blob) return setFailed(true);
      url = URL.createObjectURL(blob);
      setSrc(url);
    });
    return () => {
      live = false;
      if (url) URL.revokeObjectURL(url);
    };
  }, [sessionId]);
  if (failed) return <p role="status" className="n-muted">{m1Briefing.videoFailed}</p>;
  if (!src) return <p role="status" className="n-muted">{m1Briefing.videoLoading}</p>;
  return <video className="m1-video" controls preload="metadata" src={src} aria-label={m1Briefing.videoLabel} />;
}

export default function VideoSlot({ sessionId, video }: { sessionId: string; video: BriefingView["video"] }) {
  if (video.mode === "none") return null;
  return (
    <Panel label={m1Briefing.videoTitle} className="m1-video-panel">
      {video.mode === "file" ? (
        <FileVideo sessionId={sessionId} />
      ) : (
        <div className="n-empty m1-video-placeholder">
          <strong className="etitle">{m1Briefing.videoPlaceholder}</strong>
          <span className="n-muted ebody">{m1Briefing.videoPlaceholderNote}</span>
        </div>
      )}
    </Panel>
  );
}
