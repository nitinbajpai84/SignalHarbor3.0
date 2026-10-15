import type { MouseEvent, ReactNode } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { PageFrame } from "../../design";
import CasesPage from "../e4/CasesPage";
import EvidencePage from "../e2/EvidencePage";
import ActionToday from "./ActionToday";
import CaseView from "./CaseView";
import ManagersInbox from "../k5/ManagersInbox";
import ReconPage from "./ReconPage";

// ACT1: /centre/action is one page (ActionToday). The old tab routes stay as deep links to the full pages: Cases, Reconciliations, Managers.
// Tickets (/centre/tickets) and the Review queue (/centre/extract/review) have always been routes of their own.
type Tab = "today" | "cases" | "recon" | "managers";
const TITLES: Record<Exclude<Tab, "today">, string> = { cases: "Cases", recon: "Reconciliations", managers: "Managers" };
// The reused pages link to their old homes; keep the person inside this centre.
const HOME: [string, string][] = [["/centre/desk/", "/centre/action/cases/"], ["/centre/evidence/", "/centre/action/evidence/"], ["/centre/desk", "/centre/action/cases"], ["/centre/evidence", "/centre/action/evidence"]];

export function Stay({ children }: { children: ReactNode }) {
  const go = useNavigate();
  const onClick = (e: MouseEvent) => {
    const a = (e.target as HTMLElement).closest("a");
    const href = a?.getAttribute("href") ?? "";
    const hit = HOME.find(([from]) => href === from || href.startsWith(from));
    if (!a || !hit || e.metaKey || e.ctrlKey) return;
    e.preventDefault();
    go(hit[1] + href.slice(hit[0].length));
  };
  return <div onClick={onClick}>{children}</div>;
}

export const ActionEvidence = () => <Stay><EvidencePage /></Stay>;

export default function ActionCentre({ tab }: { tab: Tab }) {
  const { caseId } = useParams();
  if (tab === "today") return <Stay><ActionToday /></Stay>;
  return (
    <>
      <PageFrame title={TITLES[tab]} crumbs={<Link className="ds-link" to="/centre/action">Back to today</Link>}>{null}</PageFrame>
      <Stay>
        {tab === "recon" ? <ReconPage /> : tab === "managers" ? <ManagersInbox /> : caseId ? <CaseView /> : <CasesPage framed />}
      </Stay>
    </>
  );
}
