import type { ReactNode } from "react";

import { copy } from "../copy";
import BrandMark from "./BrandMark";
import ThemeControl from "./ThemeControl";

const style = `
  .guest-page { min-height: 100vh; background: var(--bg); color: var(--text-primary); padding: 16px; display: flex; justify-content: center; }
  .guest-card { width: 100%; max-width: 760px; display: flex; flex-direction: column; gap: 16px; }
  .guest-header { display: flex; align-items: center; gap: 12px; padding: 8px 0; }
  .guest-header strong { font-family: var(--font-heading); font-size: 18px; }
  .guest-spacer { flex: 1; }
  .guest-title { font-family: var(--font-heading); font-size: 22px; font-weight: 700; margin: 0; color: var(--text-primary); }
  .guest-body { background: var(--surface-elevated); border: 1px solid var(--border-hairline); border-radius: var(--radius-lg); padding: 24px 20px; display: flex; flex-direction: column; gap: 14px; }
`;

/** The look for the pages behind a link: Signal Harbor header and theme choice, no signed-in top bar, content in one card. */
export default function GuestShell({ title, children }: { title: string; children: ReactNode }) {
  return (
    <>
      <style>{style}</style>
      <div className="guest-page">
        <div className="guest-card">
          <header className="guest-header">
            <BrandMark named={false} size={36} />
            <strong>{copy.product}</strong>
            <div className="guest-spacer" />
            <ThemeControl />
          </header>
          <main className="guest-body">
            <h1 className="guest-title">{title}</h1>
            {children}
          </main>
        </div>
      </div>
    </>
  );
}
