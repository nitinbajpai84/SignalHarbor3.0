# Look and feel: the earlier Signal Harbor stylesheets (decision D-027)

Nitin wants the new product to look the same as the earlier Signal Harbor ("Charter" look: grey paper, harbor navy, beam teal, copper for suggestions, Fraunces and Source Sans 3).

## What was copied (read-only copies from the earlier repo, commit 3a798cc5)

| Where | What |
|---|---|
| `ui/src/styles/legacy/sh.css` | Design tokens (colours, light and dark themes, three states: light, dark, system) and the component styles (93 KB) |
| `ui/src/styles/legacy/screens-*.css` | Per-screen styles: team rooms, intent, baseline, flow, context, foresight, peek, evidence and others |
| `ui/public/brand/` | The lighthouse mark in 32, 64, 128 and 512 px, on light and on dark |

The older prototype's `vendor/fonts` folder was not copied: it holds fonts from an earlier theme the Charter look does not use.

## How to use it in the React shell (for the P1-05 builder)

1. **Fonts.** The Charter look loads Fraunces, Source Sans 3 and JetBrains Mono from Google Fonts. Add this to `ui/index.html`:
   `<link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,wght@0,500;0,600;0,700;1,500;1,600&family=Source+Sans+3:wght@400;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet" />`
   A customer's own environment may be offline, so the fonts should be vendored into `ui/public/fonts/` before any customer install. Record that as an autonomous decision; until then keep the Google link.
2. **Import order.** Import `legacy/sh.css` first from `ui/src/main.tsx`, then only the `screens-*.css` files a module needs. Do not import all of them everywhere.
3. **Tokens first.** The tokens in `sh.css` (`--bg`, `--ink`, `--teal`, `--rail-navy`, `--suggest`, and so on) are the source of the look. The scaffold's `ui/src/styles.css` has its own small token set; replace it with the legacy tokens rather than keeping both.
4. **Class names.** The legacy component classes (`n-…`, `hiw-…`) were written for the old plain-JavaScript helpers. Reuse a class where a React component matches its meaning; do not copy the old JavaScript. Where a React component needs a style the old CSS lacks, add it in a new file next to the legacy ones.
5. **Themes.** Keep the three theme states (explicit light, explicit dark, follow the system) and the data attribute the legacy CSS expects: `:root[data-theme="dark"]` or `"light"`.
6. **Logo.** Use `ui/public/brand/signal-harbor-mark-*.png`; the top bar is light so the navy mark shows.
7. **Copy.** Screen wording still follows `.claude/rules/ui-copy.md`.

## Rules carried over from the earlier build

- The top bar stays light so the logo is visible; the left rail is navy.
- Readiness colours (green, amber, red, grey) are used for readiness only.
- True copper marks suggestions, "you decide" and North's rules; teal marks active states and agent presence.
- Dark mode must work for every screen.
