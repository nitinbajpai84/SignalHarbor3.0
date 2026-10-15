import { PageFrame } from "../design";
import ScreenState from "../components/ScreenState";

/** Scaffold body for an Intent Centre v2 screen: the shell's frame and the spec file it waits for. Each card replaces it. */
export default function IntentStub({ title, spec }: { title: string; spec: string }) {
  return (
    <PageFrame title={title}>
      <ScreenState state="empty" message={`Not available yet. Waits for file ${spec}.`} />
    </PageFrame>
  );
}
