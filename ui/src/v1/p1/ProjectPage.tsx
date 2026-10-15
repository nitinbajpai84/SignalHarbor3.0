import { useEffect, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";

import { ApiError } from "../../api/client";
import ScreenState from "../../components/ScreenState";
import { Chip, PageFrame, Pill, SideCard } from "../../design";
import { Button } from "../../design";
import { getProject, goLive, KINDS, type Kind, type Project } from "./api";
import BenchmarkSheet from "../g3/BenchmarkSheet";
import DeviationCards from "../g3/DeviationCards";
import ArtefactView from "./ArtefactView";
import { isLock, type Lock } from "../g1/api";
import LockedProject from "../g1/LockedProject";
import ProjectAccess from "../g1/ProjectAccess";

// P1: /centre/project/:pid. The project's four artefacts as documents people comment on together, and who holds which part.
const NAMES: Record<Kind, string> = { intent: "Intent of work", design: "System design", build_pack: "Build pack", brief: "Consumption brief", run_book: "Run book", benchmarks: "Benchmark sheet" };
const STAGES: Record<Project["stage"], string> = { talking: "Talking", signed: "Intent signed", designed: "Designed", built: "Built", live: "Live" };
const PARTS: [keyof Project["people"], string][] = [
  ["raiser", "Raised by"], ["sponsor", "Sponsor"], ["builder", "Builder"], ["head_of_data", "Head of data"], ["ops", "Operations"],
];

export default function ProjectPage() {
  const { pid = "" } = useParams<{ pid: string }>();
  const [p, setP] = useState<Project | Lock | null>(null);
  const [state, setState] = useState<"loading" | "error" | "refused" | "empty" | "populated">("loading");
  const [search] = useSearchParams();  // from Pulse: ?artefact=<kind>&line=<ref>&comment=<cid>
  const asked = search.get("artefact") as Kind | null;
  const [kind, setKind] = useState<Kind>(asked && KINDS.includes(asked) ? asked : "intent");
  const [attempt, setAttempt] = useState(0);
  const [refusal, setRefusal] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    getProject(pid).then((d) => { if (live) { setP(d); setState("populated"); } })
      .catch((e: unknown) => {
        if (live) setState(e instanceof ApiError && e.status === 403 ? "refused" : e instanceof ApiError && e.status === 404 ? "empty" : "error");
      });
    return () => { live = false; };
  }, [pid, attempt]);

  if (!p || state !== "populated") {
    return <PageFrame title="Project"><ScreenState state={state} onRetry={() => setAttempt((a) => a + 1)} /></PageFrame>;
  }
  if (isLock(p)) return <LockedProject lock={p} onChange={() => setAttempt((a) => a + 1)} />;
  const people = [...new Set(Object.values(p.people).filter((n): n is string => !!n))];
  const live = () => goLive(p.id).then(() => { setRefusal(null); setAttempt((a) => a + 1); })
    .catch((e: unknown) => setRefusal(e instanceof ApiError && e.message ? e.message : "That did not work. Please try again."));
  const aside = (
    <>
      <SideCard title="People on this project">
        {PARTS.map(([k, label]) => <p key={k} style={{ margin: "4px 0" }}><span className="ds-muted">{label}:</span> {p.people[k] ?? "Not named yet"}</p>)}
      </SideCard>
      {p.stage === "built" ? (
        <SideCard title="Go live">
          <p className="ds-muted">The project owner (the raiser or the sponsor) takes the project live once the build pack is signed and no comment is open. Ops then reads and comments.</p>
          <Button variant="primary" onClick={() => void live()}>Go live</Button>
          {refusal ? <p role="alert" className="ds-warn">{refusal}</p> : null}
        </SideCard>
      ) : null}
    </>
  );
  return (
    <PageFrame title={p.title || "Project"} subline={<><Pill tone="draft">{STAGES[p.stage]}</Pill> {p.title || "Project"}</>} aside={aside}>
      <ProjectAccess pid={p.id} name={p.title || undefined} />
      <div aria-label="Artefacts" style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 12 }}>
        {KINDS.map((k) => {
          const a = p.artefacts.find((x) => x.kind === k);
          return <Chip key={k} tone={k === kind ? "active" : "default"} onClick={() => setKind(k)}>{NAMES[k]}{a?.state === "signed" ? " (signed)" : ""}</Chip>;
        })}
      </div>
      <DeviationCards iid={p.intent_id} />
      {kind === "benchmarks" ? <BenchmarkSheet iid={p.intent_id} pid={p.id} /> : null}
      <ArtefactView key={kind} pid={p.id} kind={kind} people={people}
        line={kind === asked ? search.get("line") : null} comment={kind === asked ? search.get("comment") : null} />
    </PageFrame>
  );
}
