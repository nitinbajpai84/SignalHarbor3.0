import { useEffect, useRef, useState } from "react";
import { Link, NavLink, Navigate, Outlet, useLocation } from "react-router-dom";

import { getCompany, type Company } from "../api/client";
import BrandMark from "../components/BrandMark";
import ThemeControl from "../components/ThemeControl";
import { CycleBadge } from "../v1/router/CycleDate";
import ModeSwitch from "../v1/router/ModeSwitch";
import { THEME_KEY, useTheme } from "../theme";
import { useSession } from "../useSession";
import { shellText as t } from "./copy";
import { barStyle } from "./barStyle";
import { barFor, canSettings, centresFor, settingsFor } from "./roles";
import { redirectFor } from "./redirects";

/** Words for a role id: "company_admin" reads "Company admin". */
const roleWords = (r: string | undefined): string => (r ? r.charAt(0).toUpperCase() + r.slice(1).replace(/_/g, " ") : "");
const initials = (n: string): string => n.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w.charAt(0).toUpperCase()).join("") || "?";

/** The new top bar and, below it, whichever new screen the route names. */
export default function CentreShell() {
  const { user, signOut } = useSession();
  const [company, setCompany] = useState<Company | null>(null);
  const loc = useLocation();
  const refused = (loc.state as { refused?: boolean } | null)?.refused; // set by the RoleGate in App.tsx
  const [menu, setMenu] = useState<"" | "centres" | "account">("");

  const superAdmin = !!user?.roles?.includes("super_admin");
  useEffect(() => {
    let live = true;
    if (superAdmin) return () => { live = false; }; // the super admin has no company plane; these routes refuse them
    getCompany().then((c) => live && setCompany(c)).catch(() => undefined); // the bar shows the product alone
    return () => { live = false; };
  }, [superAdmin]);

  // Dark is the default: a person who has never chosen a theme gets it; their later choice is kept as usual.
  const { setChoice } = useTheme();
  useEffect(() => {
    try { if (localStorage.getItem(THEME_KEY) === null) setChoice("dark"); } catch { /* storage blocked: the device setting stands */ }
  }, [setChoice]);

  const name = user?.display_name ?? "";
  const toggle = (m: "centres" | "account") => setMenu((x) => (x === m ? "" : m));
  // The role table decides the bar (A-073). A centre that is off for the company, or not for this role, is hidden, not disabled.
  const mine = centresFor(user?.roles);
  const four = barFor(user?.roles);
  const shown = mine.size === 1 && mine.has("control") ? t.bar.filter((c) => c.id === "control") : t.centres.filter((c) => four.includes(c.id as (typeof four)[number]));
  const link = (to: string, text: string, title?: string) => <NavLink key={to} to={to} className="cs-label" title={title} onClick={() => setMenu("")}>{text}</NavLink>;
  const items = shown.map((c) => link(c.to, c.label, "title" in c ? c.title : undefined));
  // Escape and a click outside close the open menu (UX-23).
  const barRef = useRef<HTMLElement>(null);
  useEffect(() => {
    if (!menu) return;
    const key = (e: KeyboardEvent) => { if (e.key === "Escape") setMenu(""); };
    const away = (e: MouseEvent) => { if (!barRef.current?.contains(e.target as Node)) setMenu(""); };
    document.addEventListener("keydown", key); document.addEventListener("mousedown", away);
    return () => { document.removeEventListener("keydown", key); document.removeEventListener("mousedown", away); };
  }, [menu]);

  const moved = redirectFor(loc.pathname); // an old entry path goes to its new home
  if (moved) return <Navigate to={moved + loc.search} replace state={loc.state} />;

  return (
    <>
      <style>{barStyle}</style>
      <header className="cs-bar" ref={barRef}>
        <button type="button" className="cs-label cs-burger" aria-label={t.centresMenu} aria-expanded={menu === "centres"} onClick={() => toggle("centres")}>☰</button>
        <div className="cs-brand"><BrandMark named={false} size={28} /><strong>{t.product}</strong></div>
        {company ? (
          <>
            <span className="cs-div" aria-hidden="true" />
            <div className="cs-company">
              <span className="cs-chip">{company.brand?.logo ? <img src="/api/company/logo" alt="" /> : initials(company.name)}</span>
              <span className="cs-company-name">{company.name}</span>
            </div>
          </>
        ) : null}
        <nav className="cs-nav" aria-label={t.navLabel}>{items}</nav>
        {superAdmin ? null : <CycleBadge />}
        {superAdmin ? null : <ModeSwitch />}
        <div className="cs-who">
          <span className="cs-who-text">{name}</span>
          {user?.roles[0] ? <span className="cs-role cs-who-text">{roleWords(user.roles[0])}</span> : null}
          <button type="button" className="cs-avatar" aria-label={t.accountMenu} aria-expanded={menu === "account"} onClick={() => toggle("account")}>{initials(name)}</button>
        </div>
        {menu === "centres" ? <div className="cs-menu left" role="menu">{items}</div> : null}
        {menu === "account" ? (
          <div className="cs-menu" role="menu">
            <ThemeControl />
            {mine.has("control") ? <Link to="/centre/control" onClick={() => setMenu("")}>{t.control}</Link> : null}
            {canSettings(user?.roles) ? <Link to={t.settings.to} onClick={() => setMenu("")}>{t.settings.label}</Link> : null}
            {t.sections.filter((x) => settingsFor(user?.roles).has(x.to.split("/").pop() ?? "")).map((x) => <Link key={x.to} to={x.to} onClick={() => setMenu("")}>{x.label}</Link>)}
            <Link to={t.library.to} onClick={() => setMenu("")}>{t.library.label}</Link>
            {mine.has("pulse") ? <Link to={t.memory.to} onClick={() => setMenu("")}>{t.memory.label}</Link> : null}
            <button type="button" className="cs-item" onClick={() => void signOut()}>{t.signOut}</button>
          </div>
        ) : null}
      </header>
      <main className="page ds-screen">
        {refused ? <p role="status" className="ds-footnote">{t.refused}</p> : null}
        <Outlet />
      </main>
    </>
  );
}
