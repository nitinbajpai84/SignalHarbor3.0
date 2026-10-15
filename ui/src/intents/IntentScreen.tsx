import { Suspense, lazy, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { apiGet } from "../api/client";
import ScreenState from "../components/ScreenState";
import { PageFrame } from "../design";
import IntentStub from "./IntentStub";
import ProvingPanel from "./ProvingPanel";
import { AdminCancelDialog } from "./IntentAdmin";
import { useSession } from "../useSession";

/** The twelve views of ruling 1 (brief section 10) and the spec file each waits for. */
const VIEWS: Record<string, { title: string; spec: string; file: string }> = {
  wall: { title: "Think unfiltered", spec: "23", file: "WallView" },
  define: { title: "Define strategically", spec: "26", file: "DefineView" },
  charter: { title: "Charter and signature", spec: "32", file: "CharterView" },
  "build-ready": { title: "Build-ready check", spec: "33", file: "BuildReadyView" },
  session: { title: "Live session", spec: "36", file: "SessionView" },
  week: { title: "This week", spec: "38", file: "WeekView" },
  review: { title: "Review the week", spec: "40", file: "ReviewView" },
  close: { title: "Close this intent", spec: "09", file: "CloseView" },
  share: { title: "Share links", spec: "11", file: "ShareView" },
  events: { title: "What happened", spec: "16", file: "EventsView" },
  people: { title: "People and roles", spec: "06", file: "PeopleView" },
  projector: { title: "Projector view", spec: "17", file: "ProjectorView" },
};

/** The stage view per type (ruling 18: the stage view holds the type's own panels). */
const STAGE_FILE: Record<string, { file: string; spec: string }> = {
  initiative: { file: "InitiativeStageView", spec: "22" },
  brainstorm: { file: "SessionView", spec: "36" },
  pulse: { file: "WeekView", spec: "38" },
  problem: { file: "ProblemView", spec: "41" },
  decision: { file: "DecisionView", spec: "43" },
};

/* Every view module under ./views, resolved by name so a card's file mounts the moment it lands; a missing file keeps the stub. */
const MODULES = import.meta.glob("./views/*View.tsx") as Record<string, () => Promise<{ default: React.ComponentType<unknown> }>>;
const byName = (name: string) => MODULES[`./views/${name}.tsx`];

/* North's panel (file 08) sits beside every view: a dock at 1280, the bottom sheet at 390 (file 17). */
const NORTH = import.meta.glob("./NorthPanel.tsx") as Record<string, () => Promise<{ default: React.ComponentType<{ intentId: string }> }>>;
const NorthDock = NORTH["./NorthPanel.tsx"] ? lazy(NORTH["./NorthPanel.tsx"]) : null;
/* The stage clock (file 07) sits at the top of every intent view. */
const CLOCK = import.meta.glob("./StageClock.tsx") as Record<string, () => Promise<{ default: React.ComponentType<{ intentId: string }> }>>;
const Clock = CLOCK["./StageClock.tsx"] ? lazy(CLOCK["./StageClock.tsx"]) : null;
/* "Back to the check" (file 33): shown when a Fix it link from the build-ready check brought the person here. */
const BACK = import.meta.glob("./buildReady/BackToCheck.tsx") as Record<string, () => Promise<{ default: React.ComponentType<{ intentId: string }> }>>;
const BackToCheck = BACK["./buildReady/BackToCheck.tsx"] ? lazy(BACK["./buildReady/BackToCheck.tsx"]) : null;

function Lazy({ name, title, spec, intentId, head }: { name: string; title: string; spec: string; intentId: string; head?: Head }) {
  const loader = byName(name);
  if (!loader) return <IntentStub title={title} spec={spec} />;
  const C = lazy(loader);
  const projector = name === "ProjectorView";
  return (
    <Suspense fallback={<ScreenState state="loading" />}>
      <div className={projector ? undefined : "ic-with-north"}>
        <div className="ic-gutter">
          {!projector && Clock && <Clock intentId={intentId} />}
          {!projector && BackToCheck && <BackToCheck intentId={intentId} />}
          {head && <StagePanels head={head} />}
          {!projector && <Panel file="./NorthPanel.tsx" name="NorthNudge" intentId={intentId} />}
          <C />
          {head && <Panel file="./NoteToOrganiser.tsx" name="NoteToOrganiser" intentId={head.id} />}
        </div>
        {!projector && NorthDock && (
          <aside className="ic-north-dock">
            <NorthDock intentId={intentId} />
          </aside>
        )}
      </div>
    </Suspense>
  );
}

type Head = { id: string; type: string; title: string; purpose?: string; state: string; stages?: { key: string; state: string }[] };

/* Panels every stage view carries (files 06, 47): the invitation card, the people panel, the affected person's part. */
const PANELS = import.meta.glob(["./PeoplePanel.tsx", "./NoteToOrganiser.tsx", "./NorthPanel.tsx"]) as Record<string, () => Promise<Record<string, React.ComponentType<{ intentId: string }>>>>;
function Panel({ file, name, intentId }: { file: string; name: string; intentId: string }) {
  const loader = PANELS[file];
  if (!loader) return null;
  const C = lazy(() => loader().then((m) => ({ default: (m[name] ?? m.default) as React.ComponentType<{ intentId: string }> })));
  return (
    <Suspense fallback={null}>
      <C intentId={intentId} />
    </Suspense>
  );
}

/* What every stage view carries above the type's own panels (files 06, 31): the admin's cancel, the invitation card, the people panel. */
function StagePanels({ head }: { head: Head }) {
  const { user } = useSession();
  const [cancelling, setCancelling] = useState(false);
  const admin = (user?.roles ?? []).includes("company_admin") && ["open", "in_session", "closing"].includes(head.state);
  return (
    <div className="sc-wrap">
      {admin && (
        <p>
          <button type="button" className="ds-btn" onClick={() => setCancelling(true)}>Cancel this intent</button>
        </p>
      )}
      {cancelling && <AdminCancelDialog intentId={head.id} onClose={() => setCancelling(false)} onDone={() => window.location.reload()} />}
      <Panel file="./PeoplePanel.tsx" name="InvitationCard" intentId={head.id} />
      <Panel file="./PeoplePanel.tsx" name="PeoplePanel" intentId={head.id} />
    </div>
  );
}

/** The stage view when no type file exists yet: the record's head and the doors to the twelve views. */
function StageDoors({ head }: { head: Head }) {
  const open = head.stages?.find((s) => s.state === "open")?.key;
  return (
    <PageFrame title={head.title}>
      <StagePanels head={head} />
      {head.purpose && <p>{head.purpose}</p>}
      <Panel file="./NoteToOrganiser.tsx" name="NoteToOrganiser" intentId={head.id} />
      <p>
        {head.state}
        {open ? `, ${open.replace(/_/g, " ")}` : ""}
      </p>
      <ul>
        {Object.entries(VIEWS)
          .filter(([k]) => k !== "projector")
          .map(([k, v]) => (
            <li key={k}>
              <Link to={`/centre/intent/${head.id}/${k}`}>{v.title}</Link>
            </li>
          ))}
      </ul>
    </PageFrame>
  );
}

function StageView({ intentId }: { intentId: string }) {
  const [head, setHead] = useState<Head | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    apiGet<Head>(`/api/intents/${intentId}`)
      .then(setHead)
      .catch((e: { message?: string }) => setErr(e?.message ?? "Not available yet"));
  }, [intentId]);
  if (err) return <ScreenState state="empty" message="Not available yet. This intent could not be read." />;
  if (!head) return <ScreenState state="loading" />;
  const stage = STAGE_FILE[head.type];
  if (stage && byName(stage.file)) {
    const lazy = <Lazy name={stage.file} title={head.title} spec={stage.spec} intentId={intentId} head={head} />;
    // Spec 58: an Initiative with a Proving record shows its panel (it hides itself when there is none)
    return head.type === "initiative" ? <>{lazy}<ProvingPanel intentId={intentId} /></> : lazy;
  }
  return <StageDoors head={head} />;
}

/** /centre/intent/:intentId and /centre/intent/:intentId/:view. */
export default function IntentScreen() {
  const { intentId = "", view } = useParams<{ intentId: string; view?: string }>();
  if (view === undefined) return <StageView intentId={intentId} />;
  const v = VIEWS[view];
  if (!v) return <ScreenState state="empty" message="We could not find that." />;
  return <Lazy name={v.file} title={v.title} spec={v.spec} intentId={intentId} />;
}
