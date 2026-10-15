import { NavLink, useLocation } from "react-router-dom";

import { useSession } from "../useSession";
import Icon, { type IconName } from "./Icon";
import { shellCopy } from "./shellCopy";

const INTENT = "/modules/m1_intent";

function Item({ to, icon, label, end, onNavigate }: { to: string; icon: IconName; label: string; end?: boolean; onNavigate: () => void }) {
  return (
    <NavLink to={to} end={end} className={({ isActive }) => `n-nav-item${isActive ? " active" : ""}`} onClick={onNavigate}>
      <Icon name={icon} />
      <span>{label}</span>
    </NavLink>
  );
}

/**
 * The earlier prototype's navy left rail (n-nav): group labels in teal, items with the active marker, and who is signed in at the
 * foot. Links only to screens that exist: the module list, and (inside module 1) its sessions and the Prepare wizard.
 */
export default function NavRail({ id, onNavigate }: { id: string; onNavigate: () => void }) {
  const { user } = useSession();
  const inIntent = useLocation().pathname.startsWith(INTENT);
  return (
    <nav className="n-nav" id={id} aria-label={shellCopy.nav}>
      <div className="n-nav-scroll">
        <div className="n-nav-group">
          <div className="n-nav-group-label">{shellCopy.navGroup}</div>
          <Item to="/" end icon="layers" label={shellCopy.navAll} onNavigate={onNavigate} />
        </div>
        {inIntent ? (
          <div className="n-nav-group">
            <div className="n-nav-group-label">{shellCopy.navIntentGroup}</div>
            <Item to={INTENT} end icon="rooms" label={shellCopy.navSessions} onNavigate={onNavigate} />
            <Item to={`${INTENT}/prepare`} icon="plus" label={shellCopy.navNew} onNavigate={onNavigate} />
          </div>
        ) : null}
        <div className="n-nav-group">
          <div className="n-nav-group-label">{shellCopy.navCompanyGroup}</div>
          <Item to="/company/bring" icon="plus" label={shellCopy.navBring} onNavigate={onNavigate} />
          <Item to="/company/interview" icon="plus" label={shellCopy.navInterviews} onNavigate={onNavigate} />
          <Item to="/company/context" icon="scroll" label={shellCopy.navContext} onNavigate={onNavigate} />
        </div>
      </div>
      {user ? (
        <div className="n-nav-foot">
          <div className="n-viewing-as-badge">
            <div className="n-nav-who">{shellCopy.signedInAs}</div>
            <div className="n-persona-badge">{user.display_name}</div>
          </div>
        </div>
      ) : null}
    </nav>
  );
}
