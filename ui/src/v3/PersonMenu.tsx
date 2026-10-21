import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import "./person.css";
import { disablePush, enablePush, getPushConfig, install, installKind, onInstallChange, pushSupported, type PushConfig } from "../pwa";

const DISMISS_KEY = "sh_install_dismissed";
const PHONE = "(max-width: 719px)";
const kept = (): boolean => { try { return localStorage.getItem(DISMISS_KEY) === "1"; } catch { return false; } };

/** The signed-in person's name as a menu: the family portal, Install app and the notifications switch (Web Push). Reads nothing until it is opened. */
export default function PersonMenu({ name, onSignOut }: { name: string; onSignOut?: () => Promise<void> }) {
  const [open, setOpen] = useState(false);
  const [cfg, setCfg] = useState<PushConfig | null>(null);
  const [say, setSay] = useState("");
  const [kind, setKind] = useState(installKind);
  const go = useNavigate();
  const out = async () => { setOpen(false); await onSignOut?.(); go("/login", { replace: true }); };
  const box = useRef<HTMLSpanElement>(null);
  useEffect(() => onInstallChange(() => setKind(installKind())), []);
  useEffect(() => {
    if (!open) return;
    let live = true;
    getPushConfig().then((c) => { if (live) setCfg(c); }, () => { if (live) setCfg(null); });
    const away = (e: MouseEvent) => { if (box.current && !box.current.contains(e.target as Node)) setOpen(false); };
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", away);
    document.addEventListener("keydown", esc);
    return () => { live = false; document.removeEventListener("mousedown", away); document.removeEventListener("keydown", esc); };
  }, [open]);
  const toggle = async () => {
    if (!cfg?.enabled || !cfg.public_key) return;
    setSay("");
    try {
      if (cfg.subscribed) await disablePush(); else await enablePush(cfg.public_key);
      setCfg({ ...cfg, subscribed: !cfg.subscribed });
    } catch (e) {
      setSay(e instanceof Error && e.message ? e.message : "I could not change that. Please try again.");
    }
  };
  const supported = pushSupported();
  return (
    <span className="v3-person" ref={box}>
      <button type="button" className="v3-person-btn" aria-haspopup="menu" aria-expanded={open} onClick={() => setOpen((o) => !o)}>{name || "Menu"}</button>
      {open && (
        <div className="v3-person-pop" role="menu" aria-label="Your menu">
          <Link role="menuitem" to="/v3/portal" onClick={() => setOpen(false)}>Family portal</Link>
          {kind === "prompt" && <button type="button" role="menuitem" onClick={() => { void install().then(() => setOpen(false)); }}>Install app</button>}
          {kind === "ios" && <p className="v3-mute">To install: tap Share, then Add to Home Screen.</p>}
          <label className="v3-switch">
            <input type="checkbox" role="switch" aria-label="Notifications for new cards and approvals" checked={!!cfg?.subscribed}
              disabled={!supported || !cfg?.enabled} onChange={() => { void toggle(); }} />
            <span>Notifications for new cards and approvals</span>
          </label>
          {!supported && <p className="v3-mute">This browser cannot show notifications.</p>}
          {supported && cfg && !cfg.enabled && <p className="v3-mute">Notifications are not switched on for this office yet.</p>}
          <button type="button" role="menuitem" onClick={() => { void out(); }}>Sign out</button>
          {say && <p className="v3-err" role="alert">{say}</p>}
        </div>
      )}
    </span>
  );
}

/** Phones only: one dismissible line offering the app, until it is installed or the person says no. */
export function InstallBanner() {
  const [kind, setKind] = useState(installKind);
  const [gone, setGone] = useState(kept);
  useEffect(() => onInstallChange(() => setKind(installKind())), []);
  if (gone || !kind || !window.matchMedia?.(PHONE).matches) return null;
  const no = () => { setGone(true); try { localStorage.setItem(DISMISS_KEY, "1"); } catch { /* the choice lasts for this visit */ } };
  return (
    <div className="v3-install" role="region" aria-label="Install the app">
      <span>{kind === "ios" ? "Add Harbor to your home screen: tap Share, then Add to Home Screen." : "Install Signal Harbor on this phone."}</span>
      {kind === "prompt" && <button type="button" className="go" onClick={() => { void install(); }}>Install app</button>}
      <button type="button" onClick={no} aria-label="Not now">Not now</button>
    </div>
  );
}
