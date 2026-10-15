import type { ReactNode } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import PageHead from "../../components/PageHead";
import ScreenState from "../../components/ScreenState";
import { getLists, getSession, listTemplates, type Lists, type SessionView, type TemplateRow } from "./api";
import { m1, m1Companion, m1Look } from "./copy";
import NiraDock from "./NiraDock"; // M1-UI2
import PrepareWizard from "./PrepareWizard";
import SessionSummary from "./SessionSummary";
import { useLoad } from "./useLoad";

interface Loaded {
  lists: Lists;
  templates: TemplateRow[];
  session: SessionView | null;
}

interface Props {
  onUnsaved?: (unsaved: boolean) => void;
  /** Shown under the page title and above the wizard or summary (the organiser's room, on a started session). */
  above?: ReactNode;
  /** Changes when the session moves on (draft to started): the screen then reads it again. */
  version?: string;
}

/** Prepare a new session, reopen a draft, or look at one that has already started (read-only). */
export default function PrepareScreen({ onUnsaved, above, version = "" }: Props = {}) {
  const { sessionId } = useParams();
  const navigate = useNavigate();
  const { state, data, message, retry } = useLoad<Loaded>(
    async () => {
      const [lists, templates, session] = await Promise.all([
        getLists(),
        listTemplates(),
        sessionId ? getSession(sessionId) : Promise.resolve(null),
      ]);
      return { lists, templates, session };
    },
    `${sessionId ?? "new"}:${version}`,
  );
  const started = data?.session ? !data.session.editable : false;
  const title = started ? m1.summary.title : m1.wizard.title;
  const at = data?.session?.state;
  const stage = at === undefined || at === "draft" ? "prepare" : at === "lobby" ? "lobby" : "session"; // M1-UI2: what Nira explains here
  return (
    <>
      <PageHead
        title={title}
        sub={started ? undefined : m1.wizard.pageIntro}
        crumbs={[{ label: m1Look.crumbModules, to: "/" }, { label: m1.home.title, to: "/modules/m1_intent" }, { label: title }]}
        actions={
          <Link className="n-btn" to="/modules/m1_intent">
            {m1.wizard.toHome}
          </Link>
        }
      />
      {above}
      <ScreenState state={state} onRetry={retry} message={message}>
        {data && data.session && !data.session.editable ? (
          <SessionSummary session={data.session} lists={data.lists} />
        ) : data ? (
          <PrepareWizard
            lists={data.lists}
            templates={data.templates}
            existing={data.session}
            onDeleted={() => navigate("/modules/m1_intent")}
            onUnsaved={onUnsaved}
          />
        ) : null}
      </ScreenState>
      <NiraDock
        sessionId={sessionId ?? ""}
        stage={stage}
        actions={
          stage === "prepare"
            ? [{ label: m1Companion.actions.toSessions, to: "/modules/m1_intent" }]
            : [{ label: m1Companion.actions.toBriefing, to: `/modules/m1_intent/sessions/${encodeURIComponent(sessionId ?? "")}/briefing` }]
        }
      />
    </>
  );
}
