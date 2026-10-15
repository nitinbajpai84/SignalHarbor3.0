// Layout for the share panel and the visitor view: two regions at 1280, one column below 900px.
export const shareStyle = `
  .sv-grid { display: grid; grid-template-columns: 7fr 5fr; gap: 16px; align-items: start; }
  .sv-visit { display: grid; grid-template-columns: 8fr 4fr; gap: 16px; align-items: start; }
  .sv-col { display: flex; flex-direction: column; gap: 16px; min-width: 0; }
  .sv-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 8px; }
  .sv-row { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 12px; padding: 8px 0; border-bottom: 1px solid var(--border-hairline); }
  .sv-row > .sv-grow { flex: 1 1 200px; min-width: 0; }
  .sv-pick { max-height: 260px; overflow: auto; }
  .sv-pick > * { flex-shrink: 0; }
  .sv-banner { padding: 12px 16px; border-radius: var(--radius-lg); border: 1px solid var(--border-hairline); background: var(--surface-elevated); }
  .sv-field { width: 100%; box-sizing: border-box; min-height: 44px; font: inherit; color: var(--text-primary); background: var(--surface-elevated); border: 1px solid var(--border-hairline); border-radius: var(--radius-md, 8px); padding: 8px 10px; }
  textarea.sv-field { min-height: 110px; resize: vertical; }
  .sv-card { padding: 8px 10px; border: 1px solid var(--border-hairline); border-radius: var(--radius-md, 8px); background: var(--surface-elevated); }
  .sv-lanes { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 12px; }
  .sv-note { margin: 0; color: var(--text-muted); font-size: 13px; }
  .sv-link { word-break: break-all; font-family: monospace; padding: 8px; border: 1px solid var(--border-hairline); border-radius: 8px; }
  @media (max-width: 900px) { .sv-grid, .sv-visit { grid-template-columns: 1fr; } .sv-pick { max-height: 50vh; } }
`;
