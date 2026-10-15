# Posting the demo video in the briefing

Nitin asked for the guide and video and for them to be posted in the briefing. This supersedes D-029 ("no video yet, do not use brag"). The brag tool was not used; see the report (it is a promo-video skill that needs the Hyperframes CLI from the network and builds from code, not from app screens).

## Where the slot reads its file
The slot (`ui/src/modules/m1_intent/briefing/VideoSlot.tsx`) plays `GET /api/modules/m1_intent/sessions/{id}/briefing/video`. The file is stored **per session** by `PUT` on the same path (`modules/m1_intent/api/briefing.py`, `put_video`), organiser only, content type `video/mp4` or `video/webm`, at most 100 MB, only while the session is a draft, in the lobby or in the briefing. There is no global setting and no default-video file, so there is no setting to change.

## Posting it today, no code change
`python docs/guides/m1/post-video.py <32-character session id>` (reads the seed password locally, never prints it). Proven: session `5b50d3fa64b44087519a82f9b56b721a` ("Briefing video check (illustrative)") now plays the video in its briefing (`briefing-with-video.png`).

## Change needed for every future session (orchestrator to apply, code)
Today the organiser has no screen to add the video, so each session needs the script above. To make it automatic, either:
1. UI: on the organiser's session page, before "Start the briefing", add a file picker "Add the briefing video" that sends the chosen file with `PUT briefingVideoUrl(id)` (`ui/src/modules/m1_intent/api.ts` already exports `briefingVideoUrl`; send the File as the body with its `type` as Content-Type and the `X-CSRF-Token` header).
2. Default: in `modules/m1_intent/domain/briefing.py` `video_file()` / the GET route, fall back to a shared file such as `packs/_shared/briefing/module-1-demo.mp4` (copy of `docs/guides/m1/module-1-demo.mp4`) when the session has none, and make `_video_view` return `mode: "file"` for it. Needs a contract line in `contracts/briefing.yaml` for the path.
