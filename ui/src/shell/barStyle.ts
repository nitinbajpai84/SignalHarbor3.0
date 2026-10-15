// The new top bar's rules, as text so they ship with the component. Colours and type come from the app's tokens only.
export const barStyle = `
.cs-bar { display: flex; align-items: center; gap: 16px; padding: 10px 20px; background: var(--surface-elevated); border-bottom: 1px solid var(--border-hairline); position: relative; }
.cs-brand, .cs-company, .cs-who { display: flex; align-items: center; gap: 8px; min-width: 0; }
.cs-brand strong { color: var(--text-primary); }
.cs-div { width: 1px; align-self: stretch; background: var(--border-hairline); }
.cs-chip { width: 28px; height: 28px; border-radius: var(--radius-sm); border: 1px solid var(--border-hairline); display: inline-flex; align-items: center; justify-content: center; overflow: hidden; color: var(--text-muted); font-size: 12px; }
.cs-chip img { max-width: 100%; max-height: 100%; }
.cs-nav { display: flex; gap: 22px; margin: 0 auto; }
.cs-label { font-size: 14px; color: var(--text-muted); background: none; border: 0; padding: 12px 0; min-height: 40px; text-decoration: none; cursor: pointer; }
.cs-label[aria-current="page"] { color: var(--teal); border-bottom: 2px solid var(--teal); }
.cs-label:disabled { cursor: not-allowed; opacity: .6; }
.cs-role { font-size: 11px; padding: 1px 8px; border-radius: 999px; border: 1px solid var(--border-hairline); color: var(--text-muted); }
.cs-avatar { width: 40px; height: 40px; border-radius: 50%; border: 1px solid var(--teal); background: none; color: var(--teal); font-weight: 600; cursor: pointer; }
.cs-menu { position: absolute; right: 20px; top: 100%; z-index: 20; min-width: 220px; display: flex; flex-direction: column; gap: 10px; padding: 12px; background: var(--surface-elevated); border: 1px solid var(--border-hairline); border-radius: var(--radius-sm); }
.cs-menu.left { right: auto; left: 20px; }
.cs-burger { display: none; }
.cs-menu a, .cs-menu button.cs-item { color: var(--text-primary); background: none; border: 0; text-align: left; padding: 0; cursor: pointer; text-decoration: none; }
.cs-brand strong { white-space: nowrap; }
.cs-chip, .cs-avatar, .cs-burger, .cs-div { flex: none; }
@media (max-width: 720px) {
  .cs-nav, .cs-who-text, .cs-company-name { display: none; }
  .cs-burger { display: inline-flex; }
  .cs-bar { gap: 8px; padding: 8px 12px; }
  .cs-who { margin-left: auto; }
}
/* a phone (390px): the mark stands for the product and the word stays for screen readers, so the company badge and the avatar keep their room */
@media (max-width: 480px) {
  .cs-brand strong { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }
}
`;
