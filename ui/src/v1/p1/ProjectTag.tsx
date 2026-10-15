import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { isLock, type Lock } from "../g1/api";
import { projectOf, type Project } from "./api";

// P1: the link to the project page on a conversation header, in words (never the raw project id). Silent while loading or when there
// is no project.
export function useProject(iid: string): Project | Lock | null {
  const [p, setP] = useState<Project | Lock | null>(null);
  useEffect(() => {
    let live = true;
    if (iid) projectOf(iid).then((got) => { if (live) setP(got); }).catch(() => undefined);
    return () => { live = false; };
  }, [iid]);
  return p;
}

export function useProjectId(iid: string): string | null {
  return useProject(iid)?.id ?? null;
}

const STAGE: Record<string, string> = { talking: "being drafted", signed: "signed", designed: "in Build", built: "built", live: "live" };

export default function ProjectTag({ iid }: { iid: string }) {
  const p = useProject(iid);
  if (!p || isLock(p)) return null;
  const stage = STAGE[p.stage];
  return <Link className="ds-link" to={`/centre/project/${encodeURIComponent(p.id)}`}>Open the project page{stage ? ` (${stage})` : ""}</Link>;
}
