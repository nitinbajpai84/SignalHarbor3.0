import { useSearchParams } from "react-router-dom";

import { Chip } from "../../design";
import { brCopy } from "../views/buildReadyCopy";

/** Spec 33: the screen a "Fix it" link lands on carries `?back=build-ready`; this chip returns to the check, which rechecks on arrival. */
export default function BackToCheck({ intentId }: { intentId: string }) {
  const [params] = useSearchParams();
  if (params.get("back") !== "build-ready") return null;
  return (
    <p style={{ margin: "0 0 var(--ds-s2)" }}>
      <Chip href={`/centre/intent/${intentId}/build-ready?recheck=1`}>{brCopy.backToCheck}</Chip>
    </p>
  );
}
