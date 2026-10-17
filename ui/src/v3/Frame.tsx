import { useEffect, useState, type ReactNode } from "react";
import { Link, NavLink } from "react-router-dom";

import { useSession } from "../useSession";
import ModeSwitch from "../v1/router/ModeSwitch";  // Testing or Real use models, the same company switch as 2.0
import { getDesk } from "./api";
import "./v3.css";

const today = () => new Date().toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long" });
const PHONE = "(max-width: 719px)";

/** Simple line icons for the phone tab bar; aria-hidden so each link keeps its plain name. */
const Ico = ({ d }: { d: ReactNode }) => (
  <svg className="v3-ico" aria-hidden="true" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">{d}</svg>
);
const HOME = <><path d="M3 11l9-7 9 7" /><path d="M5 10v10h14V10" /></>;
const ACTION = <><path d="M12 3v2" /><path d="M6 17V11a6 6 0 0 1 12 0v6l2 2H4z" /><path d="M10 21h4" /></>;
const BUILD = <><path d="M12 3l9 5-9 5-9-5z" /><path d="M3 13l9 5 9-5" /></>;
const CONSUME = <><path d="M4 20V10" /><path d="M10 20V4" /><path d="M16 20v-7" /><path d="M22 20H2" /></>;
const KNOW = <><path d="M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2z" /><path d="M4 19V5" /></>;

/** The 3.0 page frame: logo, the four places (Action, Build, Consume, Knowledge); the logo is the Desk, the signed-in person.
 * On a phone the nav becomes a bottom tab bar with Home first and a count of what needs a person on Action. */
export default function V3Frame({ children, back }: { children: ReactNode; back?: ReactNode }) {
  const { user } = useSession();
  const [needs, setNeeds] = useState(0);
  useEffect(() => {
    // Only phones show the badge, so only phones pay for the call. One call per page; a failure just hides the badge.
    if (!window.matchMedia?.(PHONE).matches) return;
    let live = true;
    getDesk().then((d) => { if (live) setNeeds(d.needs.length); }, () => undefined);
    return () => { live = false; };
  }, []);
  return (
    <div className="v3">
      <header className="v3-top">
        <div className="v3-brandrow">
          <Link to="/v3/desk" className="v3-home" aria-label="Home: the Desk">
            <span className="v3-logo" aria-hidden="true" />
            <span className="brand">Signal Harbor</span>
          </Link>
          {back}
          <span className="v3-mute">{today()}</span>
        </div>
        <nav className="v3-nav" aria-label="Harbor">
          <NavLink to="/v3/desk" className="v3-only-phone"><Ico d={HOME} />Home</NavLink>
          <NavLink to="/v3/action"><Ico d={ACTION} />Action{needs > 0 && <span className="v3-count" aria-hidden="true">{needs}</span>}</NavLink>
          <NavLink to="/v3/build"><Ico d={BUILD} />Build</NavLink>
          <NavLink to="/v3/consume"><Ico d={CONSUME} />Consume</NavLink>
          <NavLink to="/v3/knowledge"><Ico d={KNOW} />Knowledge</NavLink>
        </nav>
        <span className="v3-mode"><ModeSwitch /></span>
        <span className="v3-mute">{user?.display_name ?? ""}</span>
      </header>
      {children}
    </div>
  );
}
