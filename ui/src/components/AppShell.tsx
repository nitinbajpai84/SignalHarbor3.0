import { useEffect, useState, type ReactNode } from "react";

import { getCompany } from "../api/client";
import { copy } from "../copy";
import BrandMark from "./BrandMark";
import Icon from "./Icon";
import NavRail from "./NavRail";
import { shellCopy } from "./shellCopy";
import ThemeControl from "./ThemeControl";
import { useSession } from "../useSession";

/**
 * The shell every signed-in screen shares, laid out as the earlier prototype's index.html does: a light top bar (mark,
 * product name and tagline, company, theme, Sign out) over a navy left rail and the page. On a phone the rail is a drawer.
 */
export default function AppShell({ children }: { children: ReactNode }) {
  const { signOut } = useSession();
  const [name, setName] = useState<string | null>(null);
  const [hasLogo, setHasLogo] = useState(false);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    let live = true;
    getCompany()
      .then((c) => {
        if (!live) return;
        setName(c.name);
        setHasLogo(Boolean(c.brand?.logo));
      })
      .catch(() => undefined); // the bar falls back to the product name; the page shows its own errors
    return () => {
      live = false;
    };
  }, []);

  useEffect(() => {
    document.body.classList.toggle("n-nav-open", open); // the legacy stylesheet's drawer switch
    return () => document.body.classList.remove("n-nav-open");
  }, [open]);

  return (
    <div className="n-app">
      <header className="n-topbar">
        <button
          type="button"
          className="n-icon-btn n-menu-btn"
          aria-label={open ? shellCopy.menuClose : shellCopy.menuOpen}
          aria-expanded={open}
          aria-controls="n-rail"
          onClick={() => setOpen((o) => !o)}
        >
          <Icon name="grid" />
        </button>
        <div className="n-brand">
          <BrandMark named={name !== null} size={36} />
          <span>
            <strong>{copy.product}</strong>
            <br />
            <small>{shellCopy.tagline}</small>
          </span>
          {name !== null ? (
            <span className="n-company">
              {hasLogo ? <img className="n-company-logo" src="/api/company/logo" alt="" height={28} /> : null}
              {name}
            </span>
          ) : null}
        </div>
        <div className="n-topbar-spacer" />
        <div className="n-topbar-actions">
          <ThemeControl />
          <button type="button" className="n-btn" onClick={() => void signOut()}>
            {copy.home.signOut}
          </button>
        </div>
      </header>
      <div className="n-body">
        <NavRail id="n-rail" onNavigate={() => setOpen(false)} />
        <main className="n-main">
          <div className="page">{children}</div>
        </main>
      </div>
    </div>
  );
}
